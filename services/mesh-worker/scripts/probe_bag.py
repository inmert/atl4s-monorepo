#!/usr/bin/env python3
"""Probe an iPad-recorded librealsense .bag and report what's actually
in it. Designed to answer the question Stream A needs settled before
defect dedup ships: do iPad bags carry a real per-frame world pose?

Usage:
    python3 probe_bag.py /path/to/scan.bag

Prints, for each stream the bag exposes:
  - librealsense UID + type + format + fps
  - frame count over the full bag
  - timestamp range
For the pose stream specifically, also samples N frames and prints:
  - translation (x, y, z) — world-frame meters
  - rotation quaternion (qw, qx, qy, qz)
  - tracker confidence
  - reconstructed 4x4 T_cw to sanity-check the rotation is unitary

Exits 0 if depth + color + pose are all present with non-zero frames.
Exits 1 otherwise (which would block the defect dedup integration).
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict

import numpy as np
import pyrealsense2 as rs

# Streams we expect the iPad recorder to write.
EXPECTED = {
    "Depth": (rs.stream.depth, True),
    "Color": (rs.stream.color, True),
    "Pose":  (rs.stream.pose,  True),  # MUST exist for dedup
    "Gyro":  (rs.stream.gyro,  False), # nice-to-have, motion stream
    "Accel": (rs.stream.accel, False),
}

POSE_SAMPLES = 5
TIMEOUT_MS   = 2000


def quat_to_matrix(qw: float, qx: float, qy: float, qz: float) -> np.ndarray:
    """Convert a unit quaternion (w, x, y, z) → 3x3 rotation matrix."""
    n = qw * qw + qx * qx + qy * qy + qz * qz
    s = 0.0 if n < 1e-12 else 2.0 / n
    return np.array([
        [1 - s * (qy * qy + qz * qz),     s * (qx * qy - qz * qw),     s * (qx * qz + qy * qw)],
        [    s * (qx * qy + qz * qw), 1 - s * (qx * qx + qz * qz),     s * (qy * qz - qx * qw)],
        [    s * (qx * qz - qy * qw),     s * (qy * qz + qx * qw), 1 - s * (qx * qx + qy * qy)],
    ])


def open_bag(path: str) -> rs.pipeline:
    cfg = rs.config()
    cfg.enable_device_from_file(path, repeat_playback=False)
    pipe = rs.pipeline()
    profile = pipe.start(cfg)
    profile.get_device().as_playback().set_real_time(False)
    return pipe, profile


def report_profiles(profile) -> dict[str, dict]:
    """List every stream profile the bag exposes — UID, type, format, fps."""
    out = {}
    for sp in profile.get_streams():
        st = sp.stream_type()
        name = st.name.capitalize()
        info = {
            "uid":     sp.unique_id(),
            "stream":  name,
            "format":  sp.format().name,
            "fps":     sp.fps(),
            "found":   True,
        }
        if sp.is_video_stream_profile():
            v = sp.as_video_stream_profile()
            info["res"] = f"{v.width()}x{v.height()}"
            info["intrinsics"] = {
                "fx": v.get_intrinsics().fx, "fy": v.get_intrinsics().fy,
                "ppx": v.get_intrinsics().ppx, "ppy": v.get_intrinsics().ppy,
                "model": v.get_intrinsics().model.name,
            }
        out[name] = info
    return out


def iterate_bag(pipe) -> tuple[dict, list]:
    """Pull every frameset, count by stream, sample pose data."""
    counts: dict[str, int] = defaultdict(int)
    timestamps: dict[str, list[float]] = defaultdict(list)
    pose_samples = []

    while True:
        try:
            fs = pipe.wait_for_frames(timeout_ms=TIMEOUT_MS)
        except RuntimeError:
            break  # end of bag
        # Composite framesets have multiple frames; iterate them all.
        for f in fs:
            name = f.profile.stream_type().name.capitalize()
            counts[name] += 1
            timestamps[name].append(f.get_timestamp())

            if name == "Pose" and len(pose_samples) < POSE_SAMPLES:
                p = f.as_pose_frame().get_pose_data()
                pose_samples.append({
                    "frame_idx":    counts[name],
                    "ts_ms":        f.get_timestamp(),
                    "tx":           p.translation.x,
                    "ty":           p.translation.y,
                    "tz":           p.translation.z,
                    "qw":           p.rotation.w,
                    "qx":           p.rotation.x,
                    "qy":           p.rotation.y,
                    "qz":           p.rotation.z,
                    "tracker_conf": p.tracker_confidence,
                    "mapper_conf":  p.mapper_confidence,
                })
    return counts, timestamps, pose_samples


def report(profiles: dict, counts: dict, timestamps: dict, pose_samples: list) -> int:
    print("=" * 72)
    print("PROFILES")
    print("=" * 72)
    for name, info in sorted(profiles.items()):
        line = f"  {name:<8} uid={info['uid']:<4} fmt={info['format']:<18} fps={info['fps']}"
        if "res" in info:
            line += f" res={info['res']}"
        print(line)
        if "intrinsics" in info:
            i = info["intrinsics"]
            print(f"           intr: fx={i['fx']:.1f} fy={i['fy']:.1f} ppx={i['ppx']:.1f} ppy={i['ppy']:.1f} model={i['model']}")

    print()
    print("=" * 72)
    print("FRAME COUNTS")
    print("=" * 72)
    for name in sorted(counts.keys()):
        ts = timestamps[name]
        if not ts:
            continue
        dur_s = (max(ts) - min(ts)) / 1000.0
        rate = len(ts) / dur_s if dur_s > 0 else 0
        print(f"  {name:<8} count={len(ts):<6} duration={dur_s:6.2f}s  effective_fps={rate:5.1f}")

    print()
    print("=" * 72)
    print("POSE SAMPLES (first %d frames)" % POSE_SAMPLES)
    print("=" * 72)
    if not pose_samples:
        print("  NO POSE FRAMES — defect dedup voxel grid cannot run on this bag.")
    else:
        for s in pose_samples:
            R = quat_to_matrix(s["qw"], s["qx"], s["qy"], s["qz"])
            R_det = float(np.linalg.det(R))
            R_unitary = abs(R_det - 1.0) < 1e-3
            T_cw = np.eye(4)
            T_cw[:3, :3] = R
            T_cw[:3,  3] = [s["tx"], s["ty"], s["tz"]]
            tag = "OK" if R_unitary else "BAD ROTATION"
            print(
                f"  f={s['frame_idx']:<4} t={s['ts_ms']:>14.3f} "
                f"pos=({s['tx']:+.3f},{s['ty']:+.3f},{s['tz']:+.3f}) "
                f"quat=({s['qw']:+.3f},{s['qx']:+.3f},{s['qy']:+.3f},{s['qz']:+.3f}) "
                f"conf=t{s['tracker_conf']}/m{s['mapper_conf']} det(R)={R_det:.4f} [{tag}]"
            )

    print()
    print("=" * 72)
    print("VERDICT")
    print("=" * 72)
    have = {name for name, c in counts.items() if c > 0}
    needed = {"Depth", "Color", "Pose"}
    missing = needed - have
    if not missing and pose_samples and all(
        abs(np.linalg.det(quat_to_matrix(s["qw"], s["qx"], s["qy"], s["qz"])) - 1.0) < 1e-3
        for s in pose_samples
    ):
        print("  PASS — depth + color + valid pose stream all present.")
        print("         Defect-dedup voxel grid can use Pose frames directly.")
        return 0
    if missing:
        print(f"  FAIL — missing streams: {sorted(missing)}")
    if not pose_samples:
        print("  FAIL — pose stream present in profiles but no pose frames decoded.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bag", help="path to .bag")
    args = ap.parse_args()

    print(f"opening {args.bag}")
    t0 = time.time()
    pipe, profile = open_bag(args.bag)
    profiles = report_profiles(profile)
    try:
        counts, ts, samples = iterate_bag(pipe)
    finally:
        pipe.stop()
    elapsed = time.time() - t0
    print(f"\nplayback done · {elapsed:.1f}s\n")
    return report(profiles, counts, ts, samples)


if __name__ == "__main__":
    sys.exit(main())
