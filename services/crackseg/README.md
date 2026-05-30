# crackseg

Surface-defect inference for the inspector overlay. Loopback-only backend (`127.0.0.1:8092`); the **console** proxies to it and the **inspector** overlays its RGBA mask on the model in view. CUDA when a GPU is present (compose reserves the L4), else CPU.

```
inspector viewer ──frame──▶ console /api/crackseg/infer ──▶ crackseg (GPU)
        ◀───────── RGBA defect mask (PNG) ─────────────────────
```

## Methods (config `method`)

| Method | What | Notes |
|---|---|---|
| **`color`** (default) | Local **colour-discrepancy** — CIELAB distance from a locally-blurred base colour. No weights. | Flags marks that differ in colour from the surrounding material; tends to over-fire on textured / multi-colour assets (tune `color_scale` / `conf_threshold`). |
| `unet` | Swappable learned model — UNet / TorchScript / state_dict. | Road-crack checkpoints (`ce`/`dice`/`dicece`/`focal`) bundled; or point `weights` at your own. |

The frame is resized **preserving aspect** (no squash); the dark background is suppressed (`ignore_dark`, eroded inward) so detections land on the lit geometry, not the silhouette.

## Swapping the model (not model-specific)

Drop a weights file into `./data/crackseg/weights/` (bind-mounted at `/weights`), set `method: unet` + `weights: <file>`, and **Restart** — no rebuild. The loader auto-detects TorchScript (`torch.jit.load`, any architecture), a pickled `nn.Module` / checkpoint, or a UNet state_dict (set `out_channels`). `GET /info` lists `available_weights`.

> A CarDD **YOLOv11 vehicle-damage** model (crack/dent/scratch via Ultralytics) was prototyped as a closer-domain option and can be re-added as a `yolo` method — see [HANDOFF.md](../../HANDOFF.md) open items.

## Configuration (Pipelines page → CrackSeg)

| Field | Default | What it does |
|---|---|---|
| `method` | `color` | `color` or `unet`. |
| `conf_threshold` | `0.5` | Min score to overlay. |
| `color_blur` | `25` | Colour method: local-base window (px). |
| `color_scale` | `22` | Colour method: CIELAB deviation mapped to score 1.0 — **lower = more sensitive**. |
| `ignore_dark` | `true` | Detect only on the lit foreground (drops the silhouette). |
| `input_size` | `512` | Inference size (multiple of 16). |
| `weights` / `out_channels` / `crack_index` / `normalize` | — | UNet method. |
| `overlay_color` / `max_alpha` | `#ff3b30` / `0.7` | Overlay appearance. |

Config lives at `console/config/pipelines/crackseg.yaml` (bind-mounted RO); read at startup — **Restart to apply**.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz`, `/info` | Liveness; method, device, available weights. |
| `POST` | `/infer` | Raw image body → RGBA defect-mask PNG sized to the input. |

## Build + run

```bash
docker compose build crackseg
docker compose up -d crackseg     # or Start from the console Pipelines page
```

The bundled UNet checkpoints pickle `crackseg.models.unet.*` instances, so that package is vendored at exactly that path for `torch.load`.
