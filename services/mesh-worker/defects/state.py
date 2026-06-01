"""Online voxel-hash defect tracker.

Per docs/DEFECT_DEDUP_ONLINE.md. State machine:

    candidate  -> hits >= MIN_HITS ->  confirmed (defect_id assigned)

When a voxel promotes to confirmed, a 6-neighbor BFS pulls in adjacent
candidate voxels under the same defect_id and merges any neighboring
confirmed defects (lowest hex id wins, the other relabels).

Stable identity across re-runs:
    defect_id = sha1(scan_id | seed_voxel)[:12]

On re-analysis, prior defects.json is read and `voxel_keys` are seeded
into the grid as already-confirmed under their prior defect_id before
processing starts. The same physical voxels therefore mint the same ids.
"""
from __future__ import annotations

import hashlib
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

from .grid import (
    VOXEL_M,
    Voxel,
    build_T_cw,
    group_by_voxel,
    project_to_world,
)

log = logging.getLogger("mesh-worker.defect-tracker")

MIN_HITS = int(os.environ.get("ARACHNID_DEFECT_MIN_HITS", "3"))

# Confidence filters applied at flush() time. Without these the big bag
# produces 500+ "defects" because crackseg in `color` mode (CIELAB local
# deviation) flags any bright/contrasty pixel — most of those land in
# 1-2 voxel clusters with very few hits and aren't real cracks.
#
# MIN_VOXELS_PER_DEFECT     drop a confirmed cluster smaller than N voxels.
#                           At 4 cm voxels: N=3 cuts everything under ~190 cm³.
# MIN_TOTAL_HITS_PER_DEFECT drop a cluster whose summed voxel hit count is
#                           below T. A defect seen 12+ times across all its
#                           voxels has appeared in roughly that many frames,
#                           so a 12-hit floor maps to "appeared in at least
#                           ~12 / stride source frames" — well above noise.
MIN_VOXELS_PER_DEFECT     = int(os.environ.get("ARACHNID_DEFECT_MIN_VOXELS",      "3"))
MIN_TOTAL_HITS_PER_DEFECT = int(os.environ.get("ARACHNID_DEFECT_MIN_TOTAL_HITS", "12"))

# 6-connectivity. Defects with cells touching face-to-face merge.
# Diagonal/edge connectivity (18 or 26) would over-merge separate
# defects whose voxels happen to share a corner; 6 is the conservative pick.
NEIGHBOR_OFFSETS = [
    ( 1,  0,  0), (-1,  0,  0),
    ( 0,  1,  0), ( 0, -1,  0),
    ( 0,  0,  1), ( 0,  0, -1),
]

# Cap on raw_points held per voxel — the hull/centroid only needs a sample.
# Keeps memory bounded on long bags with many high-density defects.
RAW_POINTS_PER_VOXEL_CAP = 256


def mint_defect_id(scan_id: str, seed_voxel: tuple[int, int, int]) -> str:
    """Stable defect_id from scan_id + the first confirmed voxel's key."""
    h = hashlib.sha1(f"{scan_id}|{seed_voxel[0]},{seed_voxel[1]},{seed_voxel[2]}".encode())
    return h.hexdigest()[:12]


class DefectTracker:
    """One instance per scan. Plug into mesh-worker's frame loop as a FrameSink."""

    def __init__(
        self,
        scan_id: str,
        prior_defects: dict | None = None,
        voxel_m: float = VOXEL_M,
        min_hits: int = MIN_HITS,
    ):
        self.scan_id = scan_id
        self.voxel_m = voxel_m
        self.min_hits = min_hits
        self.grid: dict[tuple[int, int, int], Voxel] = {}
        self.frames_processed = 0
        self.frames_with_detections = 0
        # Per-defect first_seen_at; preserved across re-runs from prior.
        self.first_seen_at: dict[str, str] = {}
        # Pre-cached intrinsics (set on first frame; stays constant per scan).
        self._fx = self._fy = self._cx = self._cy = None
        self._seed_from_prior(prior_defects)

    # ── Re-run continuity ──────────────────────────────────────────────────

    def _seed_from_prior(self, prior: dict | None) -> None:
        if not prior or "defects" not in prior:
            return
        seeded = 0
        for d in prior.get("defects", []):
            did = d.get("defect_id")
            if not did:
                continue
            self.first_seen_at[did] = d.get("first_seen_at") or _now_iso()
            for vk in d.get("voxel_keys", []):
                try:
                    key = (int(vk[0]), int(vk[1]), int(vk[2]))
                except (TypeError, ValueError, IndexError):
                    continue
                if key in self.grid:
                    continue
                # Seed as already-confirmed — the prior run earned the id.
                # first_frame/last_frame = -1 so the v3 emission can tell
                # "seeded but not re-observed this run" from "real hits".
                self.grid[key] = Voxel(
                    key=key,
                    hits=self.min_hits,
                    defect_id=did,
                    raw_points=[],
                    first_frame=-1,
                    last_frame=-1,
                )
                seeded += 1
        if seeded:
            log.info("seeded %d voxels from prior defects.json (%d defects)",
                     seeded, len(self.first_seen_at))

    # ── Per-frame entrypoint (FrameSink protocol) ──────────────────────────

    def on_frame(
        self,
        frame_idx: int,
        depth_np: np.ndarray,
        color_np: np.ndarray,
        pose,
        intrinsics,
    ) -> None:
        """One frame from the bag-playback loop. `pose` may be None — frame
        is skipped (no world transform = unstable voxel keys)."""
        self.frames_processed += 1
        if pose is None:
            return

        # Lazy import — if crackseg isn't reachable on the VM, mesh path
        # still ships; only the defect tracker degrades to empty output.
        from .crackseg_client import infer_mask

        rgba = infer_mask(color_np)
        if rgba.size == 0:
            return
        mask = rgba[:, :, 3] > 0
        if not mask.any():
            return

        # Cache intrinsics once; they don't change within a scan.
        if self._fx is None:
            self._fx, self._fy = float(intrinsics.fx), float(intrinsics.fy)
            self._cx, self._cy = float(intrinsics.ppx), float(intrinsics.ppy)

        T_cw = build_T_cw(pose.translation, pose.rotation, flip_camera=True)
        p_world = project_to_world(
            mask, depth_np, self._fx, self._fy, self._cx, self._cy, T_cw,
        )
        if len(p_world) == 0:
            return
        self.frames_with_detections += 1

        by_voxel = group_by_voxel(p_world, self.voxel_m)
        confirmed_this_frame: list[Voxel] = []
        for k, pts in by_voxel.items():
            v = self.grid.get(k)
            if v is None:
                v = Voxel(
                    key=k, hits=0, defect_id=None, raw_points=[],
                    first_frame=frame_idx, last_frame=frame_idx,
                )
                self.grid[k] = v
            v.hits += 1
            v.last_frame = frame_idx
            if v.first_frame < 0:
                v.first_frame = frame_idx   # was seeded from prior, now seen
            if len(v.raw_points) < RAW_POINTS_PER_VOXEL_CAP:
                # Append up to the cap; don't bother subsampling pts itself —
                # they're already ≤ ~200 per frame per voxel after projection.
                room = RAW_POINTS_PER_VOXEL_CAP - len(v.raw_points)
                v.raw_points.extend(pts[:room].tolist())
            if v.defect_id is None and v.hits >= self.min_hits:
                v.defect_id = self._adopt_or_assign(k)
                self.first_seen_at.setdefault(v.defect_id, _now_iso())
                confirmed_this_frame.append(v)

        for v in confirmed_this_frame:
            self._merge_neighbors(v)

    # ── Cluster maintenance ────────────────────────────────────────────────

    def _adopt_or_assign(self, k: tuple[int, int, int]) -> str:
        """If any 6-neighbor is already confirmed, adopt its id. Else mint a new one."""
        for dx, dy, dz in NEIGHBOR_OFFSETS:
            n = self.grid.get((k[0] + dx, k[1] + dy, k[2] + dz))
            if n is not None and n.defect_id is not None:
                return n.defect_id
        return mint_defect_id(self.scan_id, k)

    def _merge_neighbors(self, seed: Voxel) -> None:
        """BFS-expand from `seed` over 6-neighbors. Pull candidates into
        seed's defect; relabel collisions to the lexicographically lower id."""
        queue: list[Voxel] = [seed]
        seen: set[tuple[int, int, int]] = {seed.key}
        while queue:
            v = queue.pop()
            for dx, dy, dz in NEIGHBOR_OFFSETS:
                nk = (v.key[0] + dx, v.key[1] + dy, v.key[2] + dz)
                if nk in seen:
                    continue
                n = self.grid.get(nk)
                if n is None:
                    continue
                if n.defect_id is None:
                    # Adjacent candidate — adopt into seed's defect.
                    if n.hits > 0:
                        n.defect_id = seed.defect_id
                        seen.add(nk)
                        queue.append(n)
                elif n.defect_id != seed.defect_id:
                    # Two confirmed defects collide — keep the lower hex id.
                    winner = min(seed.defect_id, n.defect_id)
                    loser = max(seed.defect_id, n.defect_id)
                    self._relabel(loser, winner)
                    seed.defect_id = winner
                    seen.add(nk)
                    queue.append(n)

    def _relabel(self, loser: str, winner: str) -> None:
        """Move every voxel currently labeled `loser` to `winner`. Also
        merge first_seen_at to the earlier of the two."""
        for v in self.grid.values():
            if v.defect_id == loser:
                v.defect_id = winner
        ls = self.first_seen_at.pop(loser, None)
        if ls is not None:
            ws = self.first_seen_at.get(winner)
            self.first_seen_at[winner] = min(ws, ls) if ws else ls

    # ── Emit v3 payload ────────────────────────────────────────────────────

    def flush(self) -> dict:
        """Build the defects.json v3 payload. Volume = voxel-count × edge³.

        Confidence pruning happens here, not during candidate-promotion:
        a defect is rejected only after we've seen its final voxel +
        hit footprint. That keeps the running grid logic simple AND lets
        an operator-tuned threshold be applied to a previously-shipped
        defects.json without re-running the whole pipeline."""
        by_defect: dict[str, list[Voxel]] = defaultdict(list)
        for v in self.grid.values():
            if v.defect_id is not None:
                by_defect[v.defect_id].append(v)

        # ── Confidence filtering ────────────────────────────────────────
        dropped_low_voxels = 0
        dropped_low_hits = 0
        retained: dict[str, list[Voxel]] = {}
        for did, voxels in by_defect.items():
            voxel_count = len(voxels)
            # Sum of hit counts across all voxels in this defect; ≈ how many
            # source frames flagged any of its pixels.
            total_hits = sum(v.hits for v in voxels)
            if voxel_count < MIN_VOXELS_PER_DEFECT:
                dropped_low_voxels += 1
                continue
            if total_hits < MIN_TOTAL_HITS_PER_DEFECT:
                dropped_low_hits += 1
                continue
            retained[did] = voxels
        by_defect = retained
        if dropped_low_voxels or dropped_low_hits:
            log.info("dedup filters dropped %d defects below MIN_VOXELS=%d, "
                     "%d below MIN_TOTAL_HITS=%d",
                     dropped_low_voxels, MIN_VOXELS_PER_DEFECT,
                     dropped_low_hits,   MIN_TOTAL_HITS_PER_DEFECT)

        defects: list[dict] = []
        for did, voxels in by_defect.items():
            voxel_count = len(voxels)
            volume_m3 = voxel_count * (self.voxel_m ** 3)
            total_hits = sum(v.hits for v in voxels)

            # Pool raw points (capped per voxel) for centroid + hull.
            raw_lists = [v.raw_points for v in voxels if v.raw_points]
            if raw_lists:
                all_pts = np.concatenate([np.asarray(rl, dtype=np.float32) for rl in raw_lists], axis=0)
                centroid = all_pts.mean(axis=0).tolist()
            else:
                # Seeded-only defect with no fresh observations this run — fall
                # back to voxel-key centroid + bump in by half a voxel.
                all_pts = np.zeros((0, 3), dtype=np.float32)
                centroid = _centroid_from_keys(voxels, self.voxel_m)

            aabb = _aabb_from_keys(voxels, self.voxel_m)
            hull_vertices = _hull_world(all_pts) if len(all_pts) >= 4 else []
            real_first = [v.first_frame for v in voxels if v.first_frame >= 0]
            real_last  = [v.last_frame  for v in voxels if v.last_frame  >= 0]
            frames_observed = max((v.hits for v in voxels), default=0)
            seen_only_in_prior = not real_first  # nothing this run touched

            defects.append({
                "defect_id":         did,
                "first_seen_at":     self.first_seen_at.get(did, _now_iso()),
                "last_seen_at":      _now_iso(),
                "frames_observed":   int(frames_observed),
                "total_hits":        int(total_hits),  # NEW — sum across all defect voxels
                "first_frame":       int(min(real_first)) if real_first else -1,
                "last_frame":        int(max(real_last))  if real_last  else -1,
                "voxel_count":       int(voxel_count),
                "volume_m3":         float(volume_m3),
                "centroid_world":    [float(c) for c in centroid],
                "aabb_world":        aabb,
                "hull_world":        hull_vertices,
                "voxel_keys":        sorted([list(v.key) for v in voxels]),
                "operator_status":   "open" if not seen_only_in_prior else "stale",
                "operator_notes":    "",
            })

        # Largest volume first — feeds the PDF report's top-N section.
        defects.sort(key=lambda d: d["volume_m3"], reverse=True)

        return {
            "schema":                  "arachnid.defects/v3",
            "scan_id":                 self.scan_id,
            "voxel_size_m":            self.voxel_m,
            "min_hits":                self.min_hits,
            "min_voxels_per_defect":   MIN_VOXELS_PER_DEFECT,
            "min_total_hits_per_defect": MIN_TOTAL_HITS_PER_DEFECT,
            "frames_processed":       self.frames_processed,
            "frames_with_detections": self.frames_with_detections,
            "dropped_low_voxels":     dropped_low_voxels,
            "dropped_low_hits":       dropped_low_hits,
            "generated_at":           _now_iso(),
            "defects":                defects,
        }


# ── helpers ───────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _aabb_from_keys(voxels: list[Voxel], voxel_m: float) -> list[list[float]]:
    ks = np.array([v.key for v in voxels], dtype=np.int64)
    lo = (ks.min(axis=0) * voxel_m).astype(float).tolist()
    hi = ((ks.max(axis=0) + 1) * voxel_m).astype(float).tolist()
    return [lo, hi]


def _centroid_from_keys(voxels: list[Voxel], voxel_m: float) -> list[float]:
    ks = np.array([v.key for v in voxels], dtype=np.float32)
    return ((ks.mean(axis=0) + 0.5) * voxel_m).astype(float).tolist()


def _hull_world(pts: np.ndarray) -> list[list[float]]:
    """3D convex hull vertex list. Falls back to a single-point list on
    degenerate inputs (colinear, coplanar with too few points)."""
    try:
        import open3d as o3d  # heavy; only import here
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pts.astype(np.float64))
        hull, _ = pcd.compute_convex_hull()
        return np.asarray(hull.vertices, dtype=np.float64).tolist()
    except Exception as e:
        log.debug("hull fallback (degenerate pts? n=%d): %s", len(pts), e)
        return pts.mean(axis=0).reshape(1, 3).tolist()
