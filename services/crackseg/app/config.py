"""Crackseg configuration. Read once at startup; the console's Pipelines page
writes the yaml and Restart applies it (mirrors perception-lidar).

The service is model-agnostic: `weights` can name a bundled checkpoint OR any
file dropped into the mounted weights dir (TorchScript, a pickled module, or a
UNet-compatible state_dict). The output knobs let an arbitrary model's head be
interpreted without code changes.
"""

import os
from pathlib import Path

import yaml

CRACKSEG_BIND = os.environ.get('CRACKSEG_BIND', '127.0.0.1')
CRACKSEG_PORT = int(os.environ.get('CRACKSEG_PORT', '8092'))

# Bundled checkpoints (baked into the image) and a bind-mounted dir for the
# user's own weights (drop files in ./data/crackseg/weights on the host).
WEIGHTS_DIR = Path(os.environ.get('CRACKSEG_WEIGHTS_DIR', '/app/weights'))
CUSTOM_WEIGHTS_DIR = Path(os.environ.get('CRACKSEG_CUSTOM_WEIGHTS_DIR', '/weights'))
BUILTINS = ('ce', 'dice', 'dicece', 'focal')

CONFIG_PATH = Path(os.environ.get('CRACKSEG_CONFIG', '/app/config/pipelines/crackseg.yaml'))

DEFAULTS = {
    'method': 'color',          # 'color' (colour-discrepancy, no weights) or 'unet' (learned model)
    'conf_threshold': 0.5,      # min score to overlay (0..1)
    # --- color method ---
    'color_blur': 25,           # local-base window (px at inference size); larger = broader base
    'color_scale': 22,          # CIELAB deviation that maps to score 1.0; lower = more sensitive
    # --- shared ---
    'ignore_dark': True,        # restrict detection to the lit foreground (drops the silhouette)
    'dark_threshold': 0.06,     # luminance below this is background
    'input_size': 512,          # longest side for inference (coerced to a multiple of 16)
    # --- unet method ---
    'weights': 'dicece',        # bundled name OR a filename in the mounted weights dir
    'out_channels': 2,          # only used to build a UNet for a raw state_dict
    'crack_index': 1,           # for multi-channel output, which channel is "crack"
    'normalize': 'scale',       # 'scale' (/255) or 'imagenet'
    # --- overlay ---
    'overlay_color': '#ff3b30',
    'max_alpha': 0.7,
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.is_file():
        try:
            data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
            if isinstance(data, dict):
                cfg.update({k: data[k] for k in DEFAULTS if k in data})
        except Exception:
            pass
    return cfg
