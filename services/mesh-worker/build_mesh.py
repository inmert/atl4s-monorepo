"""mesh-worker/build_mesh.py — Poisson mesh + online defect dedup.

Per Pub/Sub message:
  1. Skip if gs://{GCS_BUCKET}/{site}/{scan}/mesh.ply already exists
     (idempotency — Pub/Sub may redeliver after timeouts)
  2. Fetch scan.bag from S3 via Vercel's /api/aws/bag/get-url
     presigned URL — no AWS credentials live on Cloud Run
  3. Mirror scan.bag → GCS so re-runs and downstream tools have a
     same-region copy
  4. pyrealsense2 playback through `for_each_frame_with_sinks()`. Two
     sinks share the single playback:
       MeshAccumulator   → Open3D RGBD frames → accumulated PointCloud
       DefectTracker     → crackseg HTTP + voxel-hash dedup
  5. MeshAccumulator: estimate normals → Poisson reconstruction →
     trim 5% low-density verts → vertex colors → mesh.ply
  6. DefectTracker: flush() → defects.json v3 (schema in
     docs/DEFECT_DEDUP_ONLINE.md). Seeded with prior defects.json if
     present so defect_ids survive re-runs.
  7. Upload mesh.ply + defects.json to GCS, push both to S3 via
     /api/aws/bag/upload-url so the INSPECT MESH/DEFECT tabs can render
     and the PDF report builder can consume the per-defect record.
"""
from __future__ import annotations
import json
import logging
import os
import tempfile
import time
from typing import Protocol

import numpy as np
import open3d as o3d
import pyrealsense2 as rs
import requests
from google.cloud import storage

from defects.grid import build_T_cw
from defects.state import DefectTracker

log = logging.getLogger("mesh-worker.build")

VERCEL_API   = os.environ.get("VERCEL_API", "https://arachnid-flight.vercel.app").rstrip("/")
GCS_BUCKET   = os.environ.get("GCS_BUCKET", "arachnid-rosbag-bucket")

VOXEL          = float(os.environ.get("MESH_VOXEL", "0.02"))
DEPTH_TRUNC    = float(os.environ.get("MESH_DEPTH_TRUNC", "5.0"))
POISSON_DEPTH  = int(os.environ.get("MESH_POISSON_DEPTH", "9"))
FRAME_STRIDE   = int(os.environ.get("MESH_FRAME_STRIDE", "4"))
MIN_POINTS     = int(os.environ.get("MESH_MIN_POINTS", "1000"))

# Reused across requests inside one container instance.
_gcs_client = None
def gcs() -> storage.Client:
    global _gcs_client
    if _gcs_client is None:
        _gcs_client = storage.Client()
    return _gcs_client


# ── Vercel presigned-URL bridge ────────────────────────────────────────────

def vercel_get_url(site_id: str, scan_id: str, part: str) -> str:
    r = requests.get(
        f"{VERCEL_API}/api/aws/bag/get-url"
        f"?site_id={site_id}&scan_id={scan_id}&part={part}",
        timeout=30,
    )
    r.raise_for_status()
    j = r.json()
    if not j.get("ok") or not j.get("url"):
        raise RuntimeError(f"get-url failed: {j}")
    return j["url"]


def vercel_upload_url(site_id: str, scan_id: str, part: str, content_type: str) -> str:
    r = requests.post(
        f"{VERCEL_API}/api/aws/bag/upload-url",
        json={"site_id": site_id, "scan_id": scan_id,
              "part": part, "content_type": content_type},
        timeout=20,
    )
    r.raise_for_status()
    j = r.json()
    if not j.get("ok") or not j.get("url"):
        raise RuntimeError(f"upload-url failed: {j}")
    return j["url"]


# ── S3 ⇄ local ⇄ GCS transfers ─────────────────────────────────────────────

def fetch_bag(site_id: str, scan_id: str, out_path: str) -> int:
    url = vercel_get_url(site_id, scan_id, "scan.bag")
    log.info("downloading scan.bag → %s", out_path)
    t0 = time.time()
    with requests.get(url, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    sz = os.path.getsize(out_path)
    log.info("download done · %.1f MB in %.1fs", sz / 1024 / 1024, time.time() - t0)
    return sz


def mirror_to_gcs(local_path: str, gcs_object: str) -> None:
    blob = gcs().bucket(GCS_BUCKET).blob(gcs_object)
    blob.upload_from_filename(local_path)
    log.info("mirrored → gs://%s/%s", GCS_BUCKET, gcs_object)


def push_to_s3(local_path: str, site_id: str, scan_id: str,
               part: str, content_type: str) -> None:
    url = vercel_upload_url(site_id, scan_id, part, content_type)
    sz = os.path.getsize(local_path)
    with open(local_path, "rb") as f:
        put = requests.put(
            url, data=f,
            headers={"Content-Type": content_type, "Content-Length": str(sz)},
            timeout=600,
        )
        put.raise_for_status()
    log.info("uploaded %s to S3 (%.1f MB)", part, sz / 1024 / 1024)


def mesh_already_in_gcs(site_id: str, scan_id: str) -> bool:
    blob = gcs().bucket(GCS_BUCKET).blob(f"{site_id}/{scan_id}/mesh.ply")
    return blob.exists()


# ── Progress reporting (consumed by /api/aws/bag/queue + dashboard) ──────
#
# Pub/Sub messages carry no progress signal — once dispatched, the dashboard
# has no idea whether the worker is downloading the bag, deep in Poisson,
# or hung. We write progress.json to S3 next to mesh-request.json on every
# milestone so queue.js can surface the actual stage instead of guessing
# from sentinel age.
#
# Stages (in order):
#   bag-fetch              downloading scan.bag from S3
#   frame-loop             playing the bag through the FrameSinks
#   poisson-reconstruction Open3D Poisson + density trim
#   mesh-variants          glb + tablet + mobile Draco encode
#   renders                Open3D OffscreenRenderer (splat + path PNGs)
#   defects-flush          DefectTracker.flush() + confidence filtering
#   pdf-build              reportlab assembly
#   done                   all artifacts in S3, message ack'd
#
# Each emission overwrites the same S3 key — readers always see the latest
# state. Emission failures NEVER fail the build (the worker still runs).
PROGRESS_SCHEMA = "arachnid.progress/v1"


def emit_progress(
    site_id: str,
    scan_id: str,
    stage: str,
    started_at_iso: str | None = None,
    **extras,
) -> None:
    """Write progress.json to S3 next to mesh-request.json. Best-effort."""
    from datetime import datetime, timezone
    payload = {
        "schema":      PROGRESS_SCHEMA,
        "site_id":     site_id,
        "scan_id":     scan_id,
        "stage":       stage,
        "updated_at":  datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "started_at":  started_at_iso,
        **extras,
    }
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix=f"progress-{scan_id}-",
        ) as f:
            json.dump(payload, f)
            tmp_path = f.name
        try:
            push_to_s3(tmp_path, site_id, scan_id, "progress.json", "application/json")
        finally:
            try: os.unlink(tmp_path)
            except OSError: pass
    except Exception as e:
        # Never break the build over a progress hiccup.
        log.warning("progress emit (%s) failed: %s", stage, e)


def _slam_stats_from_pose_track(translations: list, bag_size: int) -> dict:
    """Derive the SLAM stats the report.pdf wants from the pose track we
    already collected during playback. No bag re-read needed."""
    from datetime import datetime, timezone
    n = len(translations)
    if n == 0:
        return {
            "captured_at": "—", "duration_s": "—",
            "bag_size_mb": f"{bag_size / 1024 / 1024:.1f}",
            "frame_count": 0, "pose_count": 0,
            "walked_m": "—",
            "bbox_min": ["—","—","—"], "bbox_max": ["—","—","—"],
            "bbox_size": ["—","—","—"], "volume_m3": 0.0,
        }
    pts = np.asarray(translations, dtype=np.float32)
    diffs = np.diff(pts, axis=0)
    walked = float(np.linalg.norm(diffs, axis=1).sum()) if len(diffs) else 0.0
    bb_min = pts.min(axis=0)
    bb_max = pts.max(axis=0)
    size = bb_max - bb_min
    vol = float(size[0] * size[1] * size[2])
    # Pose stream on iPad is 60 Hz; the duration estimate is good enough
    # for the operator deliverable. (Exact bag-time deltas are recoverable
    # via fs.get_timestamp() in the loop, but that's a Stage 2 refinement.)
    duration_s = n / 60.0
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", " UTC"),
        "duration_s":  f"{duration_s:.1f}",
        "bag_size_mb": f"{bag_size / 1024 / 1024:.1f}",
        "frame_count": n, "pose_count": n,
        "walked_m":    f"{walked:.2f}",
        "bbox_min":    [f"{x:.2f}" for x in bb_min.tolist()],
        "bbox_max":    [f"{x:.2f}" for x in bb_max.tolist()],
        "bbox_size":   [f"{x:.2f}" for x in size.tolist()],
        "volume_m3":   vol,
    }


def fetch_prior_defects(site_id: str, scan_id: str) -> dict | None:
    """Pull the prior defects.json from S3 if it exists. Returns None on miss.

    Used to seed DefectTracker so defect_ids are stable across re-analysis
    runs (operator notes stay attached to the same physical voxels)."""
    try:
        url = vercel_get_url(site_id, scan_id, "defects.json")
    except Exception as e:
        log.info("no prior defects.json (%s) — starting fresh", e)
        return None
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        prior = r.json()
        if not isinstance(prior, dict) or "defects" not in prior:
            log.warning("prior defects.json shape unexpected — starting fresh")
            return None
        log.info("prior defects.json found · %d defects to seed",
                 len(prior.get("defects", [])))
        return prior
    except Exception as e:
        log.info("prior defects.json fetch failed (%s) — starting fresh", e)
        return None


# ── Mesh pipeline (lifted from scripts/build-scan-mesh.py) ─────────────────

# +Y up / -Z forward → match the Three.js world the INSPECT tab renders.
_FLIP_YZ = np.array([
    [1,  0,  0, 0],
    [0, -1,  0, 0],
    [0,  0, -1, 0],
    [0,  0,  0, 1],
])


class FrameSink(Protocol):
    """One processor in the per-frame fan-out. Two implementations ship
    today (MeshAccumulator + DefectTracker); future tools can join the
    same playback by conforming to this protocol."""

    def on_frame(
        self,
        frame_idx: int,
        depth_np: np.ndarray,
        color_np: np.ndarray,
        pose,                       # pyrealsense2.pose | None
        intrinsics,                 # o3d.camera.PinholeCameraIntrinsic
    ) -> None: ...

    def flush(self): ...


class Intrinsics:
    """Lightweight bag of pinhole intrinsics — exposes BOTH pyrealsense2's
    flat attrs (fx/fy/ppx/ppy/width/height) AND lazily builds Open3D's
    PinholeCameraIntrinsic. Sinks pick whichever they want."""

    __slots__ = ("fx", "fy", "ppx", "ppy", "width", "height", "_o3d")

    def __init__(self, rs_intr):
        self.fx     = float(rs_intr.fx)
        self.fy     = float(rs_intr.fy)
        self.ppx    = float(rs_intr.ppx)
        self.ppy    = float(rs_intr.ppy)
        self.width  = int(rs_intr.width)
        self.height = int(rs_intr.height)
        self._o3d   = None

    @property
    def o3d(self):
        if self._o3d is None:
            self._o3d = o3d.camera.PinholeCameraIntrinsic(
                width=self.width, height=self.height,
                fx=self.fx, fy=self.fy, cx=self.ppx, cy=self.ppy,
            )
        return self._o3d


def for_each_frame_with_sinks(
    bag_path: str,
    sinks: list[FrameSink],
    frame_stride: int = 1,
    max_frames: int | None = None,
) -> int:
    """Single bag-playback loop that fans depth/color/pose framesets out to
    each sink. Returns the total number of source frames seen (before stride).

    Depth + color are aligned via rs.align. Pose is read via fs.get_pose_frame()
    — verified present on iPad bags by mesh-worker/scripts/probe_bag.py.

    `max_frames` (post-stride) caps the loop; primarily for smoke tests.
    """
    log.info("opening bag (stride=%d, sinks=%d, max_frames=%s)",
             frame_stride, len(sinks), max_frames)
    cfg = rs.config()
    cfg.enable_device_from_file(bag_path, repeat_playback=False)
    pipe = rs.pipeline()
    profile = pipe.start(cfg)
    profile.get_device().as_playback().set_real_time(False)

    try:
        depth_intr_rs = profile.get_stream(rs.stream.depth).as_video_stream_profile().get_intrinsics()
    except Exception:
        pipe.stop()
        raise RuntimeError("bag has no depth intrinsics — can't deproject")

    has_color = any(s.stream_type() == rs.stream.color for s in profile.get_streams())
    has_pose  = any(s.stream_type() == rs.stream.pose  for s in profile.get_streams())
    align = rs.align(rs.stream.depth) if has_color else None
    if not has_pose:
        log.warning("bag has NO pose stream — defect tracker will skip every frame")

    intr = Intrinsics(depth_intr_rs)

    frame_count = 0
    processed = 0
    t0 = time.time()
    while True:
        try:
            fs = pipe.wait_for_frames(timeout_ms=2000)
        except RuntimeError:
            break  # end of bag
        if align is not None:
            fs = align.process(fs)
        depth = fs.get_depth_frame()
        color = fs.get_color_frame() if has_color else None
        pose  = fs.get_pose_frame()  if has_pose  else None
        if not depth:
            continue
        frame_count += 1
        if frame_count % frame_stride != 0:
            continue

        depth_np = np.asanyarray(depth.get_data())   # uint16 mm
        if color is not None:
            color_np = np.asanyarray(color.get_data())
            # iPad bags ship BGRA8 (see RSBagRecorder.swift). Handle BGR too
            # for the D455 swap-in.
            if color_np.ndim == 3 and color_np.shape[2] == 4:
                color_np = color_np[:, :, [2, 1, 0]].copy()   # BGRA → RGB (drop A)
            elif color_np.ndim == 3 and color_np.shape[2] == 3:
                color_np = color_np[:, :, ::-1].copy()        # BGR  → RGB
        else:
            color_np = np.full(depth_np.shape + (3,), 180, dtype=np.uint8)

        pose_data = pose.as_pose_frame().get_pose_data() if pose else None

        for sink in sinks:
            try:
                sink.on_frame(frame_count, depth_np, color_np, pose_data, intr)
            except Exception as e:
                # One sink throwing must not kill the loop — log + carry on
                # so the mesh path still ships even if defect tracking blows up.
                log.exception("sink %s on_frame raised: %s", type(sink).__name__, e)

        processed += 1
        if frame_count % 50 == 0:
            log.info("  frame %d (%.1fs)", frame_count, time.time() - t0)
        if max_frames is not None and processed >= max_frames:
            log.info("hit max_frames=%d cap", max_frames)
            break

    pipe.stop()
    log.info("frame loop done · %d frames, %.1fs", frame_count, time.time() - t0)
    return frame_count


class MeshAccumulator:
    """FrameSink that builds the Poisson-input point cloud.

    Per-frame: realsense → camera-frame pcd → ARKit-world via T_cw → voxel
    downsample → add to global accum. Works WITHOUT pose (legacy path —
    just sums in camera frame, which is fine for short stationary scans
    but drifts on iPad walking bags). When pose is present, every frame
    lands in stable world coordinates."""

    def __init__(self, voxel: float, depth_trunc: float):
        self.voxel = voxel
        self.depth_trunc = depth_trunc
        self.accum = o3d.geometry.PointCloud()
        self._used_pose = 0
        self._no_pose = 0

    def on_frame(self, frame_idx, depth_np, color_np, pose, intrinsics):
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            o3d.geometry.Image(np.ascontiguousarray(color_np)),
            o3d.geometry.Image(depth_np.astype(np.uint16)),
            depth_scale=1000.0,          # mm → m
            depth_trunc=self.depth_trunc,
            convert_rgb_to_intensity=False,
        )
        cam_pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, intrinsics.o3d)
        if pose is not None:
            # build_T_cw folds in the realsense→ARKit camera flip, so one
            # transform takes the rs-frame pcd straight to ARKit world.
            T_cw = build_T_cw(pose.translation, pose.rotation, flip_camera=True)
            cam_pcd.transform(T_cw)
            self._used_pose += 1
        else:
            cam_pcd.transform(_FLIP_YZ)
            self._no_pose += 1
        cam_pcd = cam_pcd.voxel_down_sample(self.voxel)
        self.accum += cam_pcd

    def flush(self) -> o3d.geometry.PointCloud:
        log.info("mesh accumulator: %d pts (%d frames with pose, %d without)",
                 len(self.accum.points), self._used_pose, self._no_pose)
        return self.accum


def accumulate_cloud(bag_path: str, voxel: float, depth_trunc: float,
                     frame_stride: int) -> o3d.geometry.PointCloud:
    """Backward-compat wrapper around for_each_frame_with_sinks() + MeshAccumulator.
    Older call sites + tests that only want the mesh path can keep using this."""
    sink = MeshAccumulator(voxel, depth_trunc)
    for_each_frame_with_sinks(bag_path, [sink], frame_stride=frame_stride)
    return sink.flush()


class PoseAccumulator:
    """FrameSink that just records the operator's walked-path translations.
    Used by the splat/path PNG renderer so the report visualises where the
    operator went, not just what they captured."""

    def __init__(self):
        self.translations: list[tuple[float, float, float]] = []

    def on_frame(self, frame_idx, depth_np, color_np, pose, intrinsics):
        if pose is None:
            return
        # ARKit gives +Y up, -Z forward. The MeshAccumulator's _FLIP_YZ
        # rotates the mesh into the same convention, so storing the raw
        # ARKit translation here keeps everything in the same frame.
        t = pose.translation
        self.translations.append((float(t.x), float(t.y), float(t.z)))

    def flush(self) -> list[tuple[float, float, float]]:
        log.info("pose accumulator: %d pose samples", len(self.translations))
        return self.translations


def reconstruct_mesh(pcd: o3d.geometry.PointCloud,
                     voxel: float, poisson_depth: int) -> o3d.geometry.TriangleMesh:
    log.info("final downsample (voxel=%.3f)", voxel)
    pcd = pcd.voxel_down_sample(voxel)

    log.info("estimating normals")
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 4, max_nn=30))
    pcd.orient_normals_consistent_tangent_plane(20)

    log.info("Poisson reconstruction (depth=%d)", poisson_depth)
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=poisson_depth, width=0, scale=1.1, linear_fit=False)

    densities = np.asarray(densities)
    keep = densities > np.quantile(densities, 0.05)
    mesh.remove_vertices_by_mask(~keep)
    mesh.compute_vertex_normals()
    log.info("mesh: %d verts, %d tris", len(mesh.vertices), len(mesh.triangles))
    return mesh


# ── Mesh variant generation (Stream B M1) ────────────────────────────────
#
# Per docs/MOBILE_SHELL.md §2: after the full mesh is reconstructed, emit
# two extra glTF variants the device-aware /api/aws/bag/get-url endpoint
# (Stream B M2) routes mobile and tablet clients to. Open3D writes glb
# uncompressed; we shell out to `gltf-transform draco …` (installed in
# Dockerfile.vm) to apply Draco geometry compression on the shrunk variants.

import subprocess  # local to keep cold-import cost of build_mesh.py unchanged


def _run_gltf_transform_draco(in_glb: str, out_glb: str,
                              quantize_position: int = 14,
                              quantize_normal: int = 8) -> bool:
    """Run gltf-transform draco compression in-place. Returns True on success.

    Fails closed: on any subprocess error we leave `in_glb` untouched and
    return False. Caller falls back to shipping the uncompressed variant
    so a Draco toolchain blip never blocks the mesh from reaching S3."""
    try:
        cmd = [
            "gltf-transform", "draco", in_glb, out_glb,
            "--quantize-position", str(quantize_position),
            "--quantize-normal",   str(quantize_normal),
        ]
        r = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            log.warning("gltf-transform draco rc=%d stderr=%s",
                        r.returncode, r.stderr.strip()[:300])
            return False
        return True
    except FileNotFoundError:
        log.warning("gltf-transform not installed in this image — Draco skipped")
        return False
    except subprocess.TimeoutExpired:
        log.warning("gltf-transform draco timed out (>3 min)")
        return False
    except Exception as e:
        log.warning("gltf-transform draco failed: %s", e)
        return False


def build_mesh_variants(mesh: o3d.geometry.TriangleMesh, td: str) -> dict[str, str]:
    """Write mesh.glb (full quality) + mesh-tablet.glb (1/3 tris, Draco)
    + mesh-mobile.glb (1/10 tris, aggressive Draco) into `td`. Returns
    a dict mapping each variant filename to its on-disk path.

    Draco shrinks the binary by ~3-10× without changing geometry. The
    quadric decimation runs BEFORE Draco so the mobile variant is both
    smaller and lower-poly — important because runtime fps cost on
    iPhone scales with triangle count, not byte count."""
    out: dict[str, str] = {}
    n_tris = max(1, len(mesh.triangles))

    # 1. Full quality glb — what desktop INSPECT loads.
    full_path = os.path.join(td, "mesh.glb")
    full = o3d.geometry.TriangleMesh(mesh)  # copy
    o3d.io.write_triangle_mesh(full_path, full, write_ascii=False, write_vertex_colors=True)
    out["mesh.glb"] = full_path

    # 2. Tablet variant — 1/3 triangles, lighter Draco.
    tablet_tris = max(1000, n_tris // 3)
    tablet = mesh.simplify_quadric_decimation(target_number_of_triangles=tablet_tris)
    tablet.compute_vertex_normals()
    tablet_path = os.path.join(td, "mesh-tablet.glb")
    o3d.io.write_triangle_mesh(tablet_path, tablet, write_ascii=False, write_vertex_colors=True)
    tablet_draco_path = os.path.join(td, "mesh-tablet-draco.glb")
    if _run_gltf_transform_draco(tablet_path, tablet_draco_path,
                                  quantize_position=14, quantize_normal=8):
        os.replace(tablet_draco_path, tablet_path)
        log.info("tablet variant: %d tris, %.1f MB (Draco)",
                 len(tablet.triangles), os.path.getsize(tablet_path) / 1024 / 1024)
    else:
        log.info("tablet variant: %d tris, %.1f MB (uncompressed — Draco unavailable)",
                 len(tablet.triangles), os.path.getsize(tablet_path) / 1024 / 1024)
    out["mesh-tablet.glb"] = tablet_path

    # 3. Mobile variant — 1/10 triangles, aggressive Draco.
    mobile_tris = max(500, n_tris // 10)
    mobile = mesh.simplify_quadric_decimation(target_number_of_triangles=mobile_tris)
    mobile.remove_duplicated_vertices()
    mobile.remove_unreferenced_vertices()
    mobile.compute_vertex_normals()
    mobile_path = os.path.join(td, "mesh-mobile.glb")
    o3d.io.write_triangle_mesh(mobile_path, mobile, write_ascii=False, write_vertex_colors=True)
    mobile_draco_path = os.path.join(td, "mesh-mobile-draco.glb")
    if _run_gltf_transform_draco(mobile_path, mobile_draco_path,
                                  quantize_position=12, quantize_normal=7):
        os.replace(mobile_draco_path, mobile_path)
        log.info("mobile variant: %d tris, %.1f MB (Draco)",
                 len(mobile.triangles), os.path.getsize(mobile_path) / 1024 / 1024)
    else:
        log.info("mobile variant: %d tris, %.1f MB (uncompressed — Draco unavailable)",
                 len(mobile.triangles), os.path.getsize(mobile_path) / 1024 / 1024)
    out["mesh-mobile.glb"] = mobile_path

    return out


def build_mesh_for_scan(site_id: str, scan_id: str) -> dict:
    log.info("=== mesh build: site=%s scan=%s ===", site_id, scan_id)
    from datetime import datetime, timezone
    job_started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    emit = lambda stage, **kw: emit_progress(site_id, scan_id, stage, job_started, **kw)
    emit("dispatched")

    # Mesh-side idempotency: skip if mesh.ply already in GCS. The defect
    # path is intentionally NOT gated on this — a re-run that re-detects
    # defects (newer model, tuned voxel size) should still write defects.json
    # even when mesh.ply is already there. Set ARACHNID_FORCE_REBUILD=1 to
    # also rebuild the mesh.
    force = os.environ.get("ARACHNID_FORCE_REBUILD") == "1"
    skip_mesh = mesh_already_in_gcs(site_id, scan_id) and not force
    if skip_mesh:
        log.info("mesh.ply already in GCS — skipping mesh rebuild (set ARACHNID_FORCE_REBUILD=1 to override)")

    with tempfile.TemporaryDirectory(prefix="mesh-") as td:
        bag_path     = os.path.join(td, "scan.bag")
        ply_path     = os.path.join(td, "mesh.ply")
        defects_path = os.path.join(td, "defects.json")

        emit("bag-fetch")
        bag_size = fetch_bag(site_id, scan_id, bag_path)
        mirror_to_gcs(bag_path, f"{site_id}/{scan_id}/scan.bag")
        emit("frame-loop", bag_size=bag_size)

        # Two sinks share the single bag-playback loop:
        #   MeshAccumulator → mesh.ply
        #   DefectTracker   → defects.json v3
        # crackseg HTTP runs inside DefectTracker.on_frame; both sinks
        # see the same depth/color/pose framesets in lockstep.
        prior = fetch_prior_defects(site_id, scan_id)
        sinks: list[FrameSink] = []
        mesh_sink = None
        defect_sink = None
        pose_sink = PoseAccumulator()
        if not skip_mesh:
            mesh_sink = MeshAccumulator(VOXEL, DEPTH_TRUNC)
            sinks.append(mesh_sink)
        sinks.append(pose_sink)
        defect_sink = DefectTracker(scan_id, prior_defects=prior)
        sinks.append(defect_sink)

        for_each_frame_with_sinks(bag_path, sinks, frame_stride=FRAME_STRIDE)

        result: dict = {
            "site_id":          site_id,
            "scan_id":          scan_id,
            "bag_size":         bag_size,
            "mesh_skipped":     skip_mesh,
            "frames_processed": defect_sink.frames_processed,
        }

        # ── Mesh: Poisson reconstruct + ship ──────────────────────────────
        if mesh_sink is not None:
            emit("poisson-reconstruction", frames=defect_sink.frames_processed)
            pcd = mesh_sink.flush()
            if len(pcd.points) < MIN_POINTS:
                raise RuntimeError(
                    f"not enough points to reconstruct ({len(pcd.points)} < {MIN_POINTS})")
            mesh = reconstruct_mesh(pcd, VOXEL, POISSON_DEPTH)
            emit("mesh-variants", verts=len(mesh.vertices), tris=len(mesh.triangles))

            # Legacy mesh.ply — the current dashboard loads this directly.
            o3d.io.write_triangle_mesh(
                ply_path, mesh,
                write_ascii=False, write_vertex_colors=True,
            )
            mesh_size = os.path.getsize(ply_path)
            mirror_to_gcs(ply_path, f"{site_id}/{scan_id}/mesh.ply")
            push_to_s3(ply_path, site_id, scan_id, "mesh.ply", "model/ply")

            # Three glb variants for device-aware serving (Stream B M1+M2):
            # mesh.glb (full), mesh-tablet.glb (1/3 + Draco), mesh-mobile.glb
            # (1/10 + Draco). See docs/MOBILE_SHELL.md §2.
            variants = build_mesh_variants(mesh, td)
            variant_sizes: dict[str, int] = {}
            for fname, path in variants.items():
                if not os.path.isfile(path):
                    continue
                sz = os.path.getsize(path)
                variant_sizes[fname] = sz
                try:
                    mirror_to_gcs(path, f"{site_id}/{scan_id}/{fname}")
                    push_to_s3(path, site_id, scan_id, fname, "model/gltf-binary")
                except Exception as e:
                    # One variant failing to ship shouldn't bring down the others.
                    log.exception("variant %s upload failed: %s", fname, e)
                    variant_sizes[fname + "_error"] = str(e)

            result.update({
                "mesh_size":     mesh_size,
                "verts":         len(mesh.vertices),
                "tris":          len(mesh.triangles),
                "variant_sizes": variant_sizes,
            })

            # ── Splat + path PNGs for the PDF report ─────────────────────
            # The PDF builder used to drive the live INSPECT page in
            # Playwright, but headless WebGL produced blank panels. Render
            # the same images server-side via Open3D's OffscreenRenderer,
            # ship them to S3, and the PDF just fetches + embeds.
            emit("renders")
            try:
                from renders import render_splat_and_path
                splat_path  = os.path.join(td, "splat.png")
                path_path   = os.path.join(td, "path.png")
                status = render_splat_and_path(
                    mesh, pose_sink.translations, splat_path, path_path,
                )
                if status:
                    log.info("renders %s", status)
                    for fname, p in (("splat.png", splat_path), ("path.png", path_path)):
                        if not os.path.isfile(p):
                            continue
                        try:
                            mirror_to_gcs(p, f"{site_id}/{scan_id}/{fname}")
                            push_to_s3(p, site_id, scan_id, fname, "image/png")
                        except Exception as e:
                            log.exception("%s upload failed: %s", fname, e)
                else:
                    log.warning("offscreen render returned None — PDF will fall back to placeholder")
            except Exception as e:
                # Rendering is opportunistic — never fail the build over it.
                log.exception("renders raised: %s", e)

        # ── Defects: serialize + ship v3 ──────────────────────────────────
        emit("defects-flush", grid_voxels=len(defect_sink.grid))
        payload = defect_sink.flush()
        with open(defects_path, "w") as f:
            json.dump(payload, f)
        defects_size = os.path.getsize(defects_path)
        try:
            mirror_to_gcs(defects_path, f"{site_id}/{scan_id}/defects.json")
            push_to_s3(defects_path, site_id, scan_id, "defects.json", "application/json")
            result["defects"] = len(payload.get("defects", []))
            result["defects_size"] = defects_size
            log.info("defects.json shipped · %d defects, %d bytes",
                     result["defects"], defects_size)
        except Exception as e:
            # Mesh already shipped; defect upload failure shouldn't 500
            # the whole job. Log + report the partial result.
            log.exception("defects.json upload failed: %s", e)
            result["defects_error"] = str(e)

        # ── Operator-deliverable PDF (report.pdf) ─────────────────────────
        # Built inline now that splat/path/defects are all in `td`. Pushes
        # to S3 next to the other artifacts; consumers can fetch via
        # /api/aws/bag/get-url?part=report.pdf. Build failure does not
        # break the rest of the job — operator can re-run a PDF-only build
        # from the existing defects.json + PNGs later if needed.
        emit("pdf-build", defects=len(payload.get("defects", [])))
        try:
            from report import build_report
            slam_stats = _slam_stats_from_pose_track(pose_sink.translations, bag_size)
            pdf_path = os.path.join(td, "report.pdf")
            ok = build_report(
                site_id=site_id, scan_id=scan_id,
                defects_payload=payload,
                splat_png_path=os.path.join(td, "splat.png"),
                path_png_path=os.path.join(td, "path.png"),
                slam_stats=slam_stats,
                out_path=pdf_path,
            )
            if ok and os.path.isfile(pdf_path):
                mirror_to_gcs(pdf_path, f"{site_id}/{scan_id}/report.pdf")
                push_to_s3(pdf_path, site_id, scan_id, "report.pdf", "application/pdf")
                result["report_size"] = os.path.getsize(pdf_path)
                log.info("report.pdf shipped · %.1f KB",
                         result["report_size"] / 1024)
        except Exception as e:
            log.exception("report.pdf build failed: %s", e)

        emit("done", defects=result.get("defects"), report_size=result.get("report_size"))
        return result
