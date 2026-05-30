"""Crack / surface-anomaly inference. Two interchangeable methods (config
`method`):

- ``color`` — local colour-discrepancy detector (no weights). Converts the frame
  to CIELAB, measures each pixel's deviation from its locally-averaged base
  colour, and flags the outliers. Thin scratches/cracks read as strong local
  deviations against a smooth base, so this finds marks that differ in colour
  from the surrounding material regardless of what the asset is.
- ``unet`` — a swappable learned model (TorchScript / pickled module / UNet
  state_dict) loaded from a bundled checkpoint or the mounted weights dir.

Both resize preserving aspect (no squash), restrict detection to the lit
foreground (eroded, so the silhouette isn't flagged), and return an RGBA mask
sized to the frame.
"""

import io
import logging

import cv2
import numpy as np
import torch
from PIL import Image

from crackseg.models.unet import UNet
from app.config import BUILTINS, CUSTOM_WEIGHTS_DIR, WEIGHTS_DIR, load_config

log = logging.getLogger('crackseg.infer')

_EXTS = ('.pt', '.pth', '.ts', '.torchscript')


def _hex_rgb(value: str) -> tuple[int, int, int]:
    h = str(value).lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 255, 59, 48


def _resolve_weights(name: str):
    if name in BUILTINS:
        return WEIGHTS_DIR / f'{name}.pt'
    for d in (CUSTOM_WEIGHTS_DIR, WEIGHTS_DIR):
        p = d / name
        if p.is_file():
            return p
    raise FileNotFoundError(f'weights "{name}" not found')


def available_weights() -> list[str]:
    out = list(BUILTINS)
    try:
        for f in sorted(CUSTOM_WEIGHTS_DIR.iterdir()):
            if f.is_file() and f.suffix.lower() in _EXTS:
                out.append(f.name)
    except Exception:
        pass
    return out


def _target_size(w: int, h: int, longest: int) -> tuple[int, int]:
    longest = max(64, longest - longest % 16)
    if w >= h:
        tw, th = longest, max(16, round(h / w * longest))
    else:
        th, tw = longest, max(16, round(w / h * longest))
    return max(16, tw - tw % 16), max(16, th - th % 16)


class Engine:
    def __init__(self) -> None:
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.cfg = load_config()
        self.method = str(self.cfg.get('method', 'color'))
        self.weights = str(self.cfg['weights'])
        self.kind = 'n/a'
        self.model = None
        if self.method == 'unet':
            self.model = self._load(_resolve_weights(self.weights))
        log.info('crackseg loaded: method=%s weights=%s kind=%s device=%s',
                 self.method, self.weights, self.kind, self.device)

    def _load(self, path):
        try:
            m = torch.jit.load(str(path), map_location=self.device)
            self.kind = 'torchscript'
            return m.eval().to(self.device)
        except Exception:
            pass
        obj = torch.load(str(path), map_location=self.device, weights_only=False)
        if isinstance(obj, torch.nn.Module):
            self.kind = 'module'
            return obj.float().eval().to(self.device)
        if isinstance(obj, dict):
            if isinstance(obj.get('model'), torch.nn.Module):
                self.kind = 'checkpoint'
                return obj['model'].float().eval().to(self.device)
            state = obj.get('state_dict') or obj.get('model') or obj
            net = UNet(in_channels=3, out_channels=int(self.cfg.get('out_channels', 2)))
            net.load_state_dict(state)
            self.kind = 'state_dict'
            return net.eval().to(self.device)
        raise RuntimeError('unsupported weights format')

    def info(self) -> dict:
        return {
            'device': str(self.device),
            'cuda': torch.cuda.is_available(),
            'method': self.method,
            'weights': self.weights,
            'kind': self.kind,
            'available_weights': available_weights(),
            **self.cfg,
        }

    # --- methods -----------------------------------------------------------

    def _color_prob(self, rgb: np.ndarray) -> np.ndarray:
        """Local colour-deviation: distance in CIELAB from a locally-blurred
        base colour. Smooth surfaces ≈ 0; scratches/marks that differ in colour
        deviate strongly."""
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype('float32')
        k = int(self.cfg.get('color_blur', 25))
        k = max(3, k | 1)  # odd
        base = cv2.GaussianBlur(lab, (k, k), 0)
        de = np.sqrt(((lab - base) ** 2).sum(axis=2))
        scale = max(1.0, float(self.cfg.get('color_scale', 22)))
        return np.clip(de / scale, 0.0, 1.0).astype('float32')

    @torch.no_grad()
    def _model_prob(self, rgb: np.ndarray) -> np.ndarray:
        arr = rgb.astype('float32').transpose(2, 0, 1) / 255.0
        if self.cfg.get('normalize') == 'imagenet':
            mean = np.array([0.485, 0.456, 0.406], dtype='float32')[:, None, None]
            std = np.array([0.229, 0.224, 0.225], dtype='float32')[:, None, None]
            arr = (arr - mean) / std
        out = self.model(torch.from_numpy(arr).unsqueeze(0).to(self.device))
        if isinstance(out, (list, tuple)):
            out = out[0]
        if out.dim() == 3:
            out = out.unsqueeze(1)
        channels = out.shape[1]
        if channels == 1:
            prob = torch.sigmoid(out)[0, 0]
        else:
            idx = min(int(self.cfg.get('crack_index', 1)), channels - 1)
            prob = torch.softmax(out, dim=1)[0, idx]
        return prob.detach().cpu().numpy().astype('float32')

    def infer_png(self, data: bytes) -> bytes:
        cfg = self.cfg
        img = Image.open(io.BytesIO(data)).convert('RGB')
        w, h = img.size

        tw, th = _target_size(w, h, int(cfg.get('input_size', 512)))
        small = np.asarray(img.resize((tw, th), Image.BILINEAR))

        prob = self._color_prob(small) if self.method == 'color' else self._model_prob(small)

        prob_full = np.asarray(
            Image.fromarray((np.clip(prob, 0, 1) * 255).astype('uint8')).resize((w, h), Image.BILINEAR)
        ).astype('float32') / 255.0

        # Restrict to the lit foreground, eroded inward so the silhouette edge
        # against the dark background isn't flagged.
        if bool(cfg.get('ignore_dark', True)):
            gray = (np.asarray(img.convert('L')).astype('float32') / 255.0)
            fg = (gray > float(cfg.get('dark_threshold', 0.06))).astype('uint8')
            fg = cv2.erode(fg, np.ones((5, 5), np.uint8), iterations=1)
            prob_full *= fg

        thr = float(cfg.get('conf_threshold', 0.5))
        max_alpha = float(cfg.get('max_alpha', 0.7))
        r, g, b = _hex_rgb(cfg.get('overlay_color', '#ff3b30'))

        mask = prob_full >= thr
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 0][mask] = r
        rgba[..., 1][mask] = g
        rgba[..., 2][mask] = b
        rgba[..., 3] = (np.where(mask, np.clip(prob_full, 0.0, 1.0) * max_alpha, 0.0) * 255).astype('uint8')

        buf = io.BytesIO()
        Image.fromarray(rgba, 'RGBA').save(buf, format='PNG')
        return buf.getvalue()
