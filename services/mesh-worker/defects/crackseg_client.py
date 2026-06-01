"""HTTP client for the loopback crackseg inference service.

crackseg runs as a Docker container on the same VM as mesh-worker,
listening on 127.0.0.1:8092 (see atl4s-monorepo/services/crackseg/app/main.py).
Same trust boundary as the console proxy at /api/crackseg — no auth.

Override with ARACHNID_CRACKSEG_URL for local dev (e.g. point at a
test container on a different port).
"""
from __future__ import annotations

import io
import logging
import os

import numpy as np
from PIL import Image
import requests

log = logging.getLogger("mesh-worker.crackseg")

CRACKSEG_URL = os.environ.get("ARACHNID_CRACKSEG_URL", "http://127.0.0.1:8092").rstrip("/")
CRACKSEG_TIMEOUT_S = float(os.environ.get("ARACHNID_CRACKSEG_TIMEOUT_S", "30"))


def infer_mask(rgb_image: np.ndarray) -> np.ndarray:
    """POST an RGB frame to crackseg, get an RGBA mask back.

    Inputs:
        rgb_image: shape (H, W, 3) uint8 RGB.
    Returns:
        rgba_mask: shape (H, W, 4) uint8 — alpha > 0 where a defect is detected.
                   Returns an all-zero array on transport error (graceful
                   degradation — the mesh path still ships).
    """
    if rgb_image.dtype != np.uint8:
        rgb_image = rgb_image.astype(np.uint8)
    if rgb_image.ndim != 3 or rgb_image.shape[2] != 3:
        log.warning("infer_mask got shape %s, expected (H, W, 3)", rgb_image.shape)
        return np.zeros(rgb_image.shape[:2] + (4,), dtype=np.uint8)

    buf = io.BytesIO()
    Image.fromarray(rgb_image, "RGB").save(buf, format="PNG")

    try:
        r = requests.post(
            f"{CRACKSEG_URL}/infer",
            data=buf.getvalue(),
            headers={"content-type": "image/png"},
            timeout=CRACKSEG_TIMEOUT_S,
        )
        r.raise_for_status()
    except Exception as e:
        log.warning("crackseg /infer failed: %s; emitting empty mask", e)
        return np.zeros(rgb_image.shape[:2] + (4,), dtype=np.uint8)

    try:
        rgba = np.array(Image.open(io.BytesIO(r.content)).convert("RGBA"))
    except Exception as e:
        log.warning("crackseg returned undecodable response: %s", e)
        return np.zeros(rgb_image.shape[:2] + (4,), dtype=np.uint8)

    # crackseg may return a mask at a different size than the input
    # (it resizes to its model's native input then back). Be defensive.
    if rgba.shape[:2] != rgb_image.shape[:2]:
        log.debug("crackseg shape mismatch: %s vs input %s",
                  rgba.shape[:2], rgb_image.shape[:2])
        rgba_img = Image.fromarray(rgba, "RGBA").resize(
            (rgb_image.shape[1], rgb_image.shape[0]), Image.NEAREST
        )
        rgba = np.array(rgba_img)
    return rgba


def is_available() -> bool:
    """Probe crackseg /info. Returns True on 2xx response within 5 s."""
    try:
        r = requests.get(f"{CRACKSEG_URL}/info", timeout=5)
        return r.status_code == 200
    except Exception:
        return False
