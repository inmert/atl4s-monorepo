"""Voxel-hash spatial primitives.

A voxel is a 3D bucket of size VOXEL_M (default 4 cm). World-frame
points get quantized to (ix, iy, iz) integer keys via floor division.
A dict[key -> Voxel] is the entire spatial index — O(1) lookup, O(N)
memory in the occupied-voxel set.

Coordinate conventions:
- librealsense camera frame: +X right, +Y down, +Z forward
- ARKit world frame:         +X right, +Y up,   -Z forward (Three.js compatible)

build_T_cw() folds the realsense→ARKit camera flip into the camera-to-world
transform by default, so callers can pass camera-frame points through one
matrix multiply and land directly in ARKit world space.
"""
from __future__ import annotations

import dataclasses
import os
from typing import Any

import numpy as np

# 4 cm — locked in via design review. Override via env for ad-hoc tuning.
VOXEL_M = float(os.environ.get("ARACHNID_DEFECT_VOXEL_M", "0.04"))

# Realsense → ARKit camera-axis flip. +Y flips down→up, +Z flips fwd→back.
_FLIP_YZ = np.array([
    [1,  0,  0, 0],
    [0, -1,  0, 0],
    [0,  0, -1, 0],
    [0,  0,  0, 1],
], dtype=np.float32)


def quat_to_R(qw: float, qx: float, qy: float, qz: float) -> np.ndarray:
    """Convert a unit quaternion (w, x, y, z) -> 3x3 rotation matrix."""
    n = qw * qw + qx * qx + qy * qy + qz * qz
    s = 0.0 if n < 1e-12 else 2.0 / n
    return np.array([
        [1 - s * (qy * qy + qz * qz),     s * (qx * qy - qz * qw),     s * (qx * qz + qy * qw)],
        [    s * (qx * qy + qz * qw), 1 - s * (qx * qx + qz * qz),     s * (qy * qz - qx * qw)],
        [    s * (qx * qz - qy * qw),     s * (qy * qz + qx * qw), 1 - s * (qx * qx + qy * qy)],
    ], dtype=np.float32)


def build_T_cw(translation: Any, rotation: Any, flip_camera: bool = True) -> np.ndarray:
    """Build a 4x4 transform that takes a point from librealsense camera frame
    to ARKit world frame.

    Inputs accept either pyrealsense2 pose attributes (`.x`, `.y`, `.z` on
    translation; `.w/.x/.y/.z` on rotation) or plain tuples in the same order.

    `flip_camera=True` (default) composes the realsense→ARKit axis flip onto
    the right side so a single matrix multiply suffices at the call site.
    """
    tx, ty, tz = (translation.x, translation.y, translation.z) if hasattr(translation, "x") else translation
    qw, qx, qy, qz = (rotation.w, rotation.x, rotation.y, rotation.z) if hasattr(rotation, "w") else rotation
    T_cw = np.eye(4, dtype=np.float32)
    T_cw[:3, :3] = quat_to_R(qw, qx, qy, qz)
    T_cw[:3,  3] = [tx, ty, tz]
    return T_cw @ _FLIP_YZ if flip_camera else T_cw


def project_to_world(
    pixel_mask: np.ndarray,
    depth_np: np.ndarray,
    fx: float, fy: float, cx: float, cy: float,
    T_cw: np.ndarray,
    min_depth_m: float = 0.05,
    max_depth_m: float = 5.0,
) -> np.ndarray:
    """Back-project mask pixels to world coords through T_cw.

    Inputs:
        pixel_mask: (H, W) bool — defective pixels.
        depth_np:   (H, W) uint16 mm.
        fx, fy, cx, cy: pinhole intrinsics in pixels (realsense camera frame).
        T_cw:       (4, 4) librealsense-camera -> ARKit-world transform.
        min/max_depth_m: drop pixels outside this range (mm zeros, far clutter).
    Returns:
        (N, 3) float32 ARKit-world coords. Empty (0, 3) array if nothing valid.
    """
    ys, xs = np.where(pixel_mask)
    if len(ys) == 0:
        return np.zeros((0, 3), dtype=np.float32)
    zs = depth_np[ys, xs].astype(np.float32) * 0.001  # mm -> m
    valid = (zs >= min_depth_m) & (zs <= max_depth_m)
    if not valid.any():
        return np.zeros((0, 3), dtype=np.float32)
    xs = xs[valid].astype(np.float32)
    ys = ys[valid].astype(np.float32)
    zs = zs[valid]
    xc = (xs - cx) * zs / fx
    yc = (ys - cy) * zs / fy
    p_cam = np.column_stack([xc, yc, zs, np.ones_like(xc)]).astype(np.float32)
    p_world = (T_cw @ p_cam.T).T[:, :3].astype(np.float32)
    return p_world


def voxel_keys(p_world: np.ndarray, voxel_m: float = VOXEL_M) -> np.ndarray:
    """(N, 3) world coords -> (N, 3) int voxel keys (floor division by voxel_m)."""
    if len(p_world) == 0:
        return np.zeros((0, 3), dtype=np.int64)
    return np.floor(p_world / voxel_m).astype(np.int64)


def group_by_voxel(p_world: np.ndarray, voxel_m: float = VOXEL_M) -> dict[tuple[int, int, int], np.ndarray]:
    """Returns dict[(ix, iy, iz) -> (M, 3) float32] grouping world points by voxel.
    Vectorized: O(N log N) via lexsort instead of per-row Python overhead."""
    if len(p_world) == 0:
        return {}
    keys = voxel_keys(p_world, voxel_m)
    # Lexsort so identical keys group as consecutive rows.
    order = np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))
    keys_sorted = keys[order]
    pts_sorted = p_world[order]
    # Find boundaries between consecutive distinct keys.
    diff = np.any(np.diff(keys_sorted, axis=0) != 0, axis=1)
    boundaries = np.concatenate([[0], np.where(diff)[0] + 1, [len(keys_sorted)]])
    out: dict[tuple[int, int, int], np.ndarray] = {}
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        k = tuple(int(c) for c in keys_sorted[start])
        out[k] = pts_sorted[start:end]
    return out


@dataclasses.dataclass
class Voxel:
    """One bucket of world-space defect detections."""
    key:         tuple[int, int, int]
    hits:        int                          # frames that flagged this voxel
    defect_id:   str | None                   # set once hits >= MIN_HITS
    raw_points:  list                         # accumulated world coords (capped)
    first_frame: int
    last_frame:  int
