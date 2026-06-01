"""mesh-worker/renders.py — offscreen rendering of static report images.

Open3D 0.18 ships with `o3d.visualization.rendering.OffscreenRenderer`,
backed by Filament + headless EGL. We use it to produce two PNGs that
the PDF report builder embeds without needing a live browser:

  splat.png       3/4 view of the reconstructed mesh + the operator's
                  walked path projected as a yellow polyline.
  path.png        Top-down (-Y) view of the same mesh and path, the
                  classic "map" panel the operator expects.

If the offscreen renderer can't be opened (no EGL device, software
fallback fails, etc.) we log + return None and let the caller fall
through to a placeholder. Mesh build never fails because of rendering.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import numpy as np

log = logging.getLogger("mesh-worker.renders")

# Where to look at and how big — small enough to keep PDFs slim
# (one panel of the report is roughly 350 × 200 pt), big enough that
# the operator can read what's there.
WIDTH       = int(os.environ.get("RENDER_WIDTH",       "1200"))
HEIGHT      = int(os.environ.get("RENDER_HEIGHT",      "800"))
PATH_COLOR  = (1.0, 0.85, 0.20)   # amber — matches the rail accent
MESH_COLOR  = (0.78, 0.79, 0.81)  # neutral grey, lets defects pop later


def _try_renderer():
    """Try to open an offscreen renderer. Returns the instance or None."""
    try:
        import open3d as o3d
        # Suppress Open3D's verbose stdout while booting headless EGL.
        o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Error)
        renderer = o3d.visualization.rendering.OffscreenRenderer(WIDTH, HEIGHT)
        return renderer
    except Exception as e:
        log.warning("OffscreenRenderer init failed: %s", e)
        return None


def _path_lineset(translations: list[tuple[float, float, float]]):
    """Build a LineSet from the operator's walked-path translations.
    Returns None if there's nothing to draw."""
    import open3d as o3d
    if len(translations) < 2:
        return None
    pts = np.asarray(translations, dtype=np.float64)
    # Stride heavily — pose stream is 60 Hz over minutes, the polyline
    # only needs ~1-2 vertices per second to read as a smooth walk.
    if len(pts) > 600:
        idx = np.linspace(0, len(pts) - 1, 600).astype(np.int64)
        pts = pts[idx]
    lines = np.array([[i, i + 1] for i in range(len(pts) - 1)], dtype=np.int32)
    colors = np.tile(PATH_COLOR, (len(lines), 1))
    ls = o3d.geometry.LineSet(
        points=o3d.utility.Vector3dVector(pts),
        lines=o3d.utility.Vector2iVector(lines),
    )
    ls.colors = o3d.utility.Vector3dVector(colors)
    return ls


def _setup_scene(renderer, mesh, path_ls):
    """Drop mesh + path into the renderer's scene with reasonable lighting."""
    import open3d as o3d
    from open3d.visualization.rendering import MaterialRecord

    scene = renderer.scene
    scene.set_background([1.0, 1.0, 1.0, 1.0])

    mesh_mat = MaterialRecord()
    mesh_mat.shader = "defaultLit"
    mesh_mat.base_color = (*MESH_COLOR, 1.0)
    mesh_mat.base_roughness = 0.8
    scene.add_geometry("mesh", mesh, mesh_mat)

    if path_ls is not None:
        line_mat = MaterialRecord()
        line_mat.shader = "unlitLine"
        line_mat.line_width = 4.0
        scene.add_geometry("path", path_ls, line_mat)

    scene.set_lighting(scene.LightingProfile.MED_SHADOWS, (0.5, -1.0, -0.5))


def _camera_aim(renderer, mesh, view: str):
    """Aim the camera at the mesh's bbox center from the requested view."""
    aabb = mesh.get_axis_aligned_bounding_box()
    centre = aabb.get_center()
    extent = max(aabb.get_extent())
    eye_dist = float(extent) * 1.6 + 1.0

    if view == "splat":
        # 3/4 cinematic view, slightly elevated
        eye = (centre[0] + eye_dist * 0.85,
               centre[1] + eye_dist * 0.55,
               centre[2] + eye_dist * 0.85)
        up = (0, 1, 0)
    elif view == "path":
        # Bird's-eye / top-down (+Y up means looking down the -Y axis)
        eye = (centre[0], centre[1] + eye_dist * 1.4, centre[2])
        up = (0, 0, -1)   # so +Z lands at the bottom of the frame
    else:
        raise ValueError(f"unknown view {view!r}")

    renderer.setup_camera(60.0, centre, eye, up)


def render_splat_and_path(
    mesh,                              # o3d.geometry.TriangleMesh
    translations: list[tuple[float, float, float]],
    splat_path: str,
    path_path: str,
) -> Optional[str]:
    """Render two PNGs from one renderer session. Returns None on failure,
    or a status string for the caller to log."""
    import open3d as o3d
    renderer = _try_renderer()
    if renderer is None:
        return None
    try:
        path_ls = _path_lineset(translations)
        _setup_scene(renderer, mesh, path_ls)

        _camera_aim(renderer, mesh, "splat")
        img = renderer.render_to_image()
        o3d.io.write_image(splat_path, img)

        _camera_aim(renderer, mesh, "path")
        img = renderer.render_to_image()
        o3d.io.write_image(path_path, img)

        return f"rendered splat={os.path.getsize(splat_path)}B path={os.path.getsize(path_path)}B"
    except Exception as e:
        log.warning("offscreen render failed: %s", e)
        return None
    finally:
        try:
            del renderer
        except Exception:
            pass
