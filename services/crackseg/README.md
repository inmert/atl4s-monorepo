# crackseg

Crack-segmentation inference. A UNet (from [yakhyo/crack-segmentation](https://github.com/yakhyo/crack-segmentation), MIT) runs on the L4 GPU and turns a rendered RGB frame into an RGBA crack mask. Loopback-only backend (`127.0.0.1:8092`); the **console** proxies to it and the **inspector** overlays its output on the model in view.

```
inspector viewer ──frame──▶ console /api/crackseg/infer ──▶ crackseg (UNet, GPU)
        ◀───────── RGBA crack mask (PNG) ──────────────────────
```

## Pipeline integration

Controlled from the console **Pipelines** page (start / stop / restart + config). Config lives at `console/config/pipelines/crackseg.yaml` (bind-mounted read-only); the container reads it at startup — **Restart to apply**.

| Field | Default | What it does |
|---|---|---|
| `weights` | `dicece` | Bundled checkpoint (`ce`/`dice`/`dicece`/`focal`) **or a filename in the mounted weights dir** (see below). |
| `conf_threshold` | `0.5` | Min crack probability to overlay. |
| `input_size` | `512` | Longest side for inference (coerced to a multiple of 16; aspect preserved). |
| `out_channels` | `2` | Only used to rebuild a UNet from a raw state_dict. |
| `crack_index` | `1` | For multi-channel output, which channel is "crack". |
| `normalize` | `scale` | `scale` (÷255) or `imagenet`. |
| `ignore_dark` | `true` | Suppress detections on the dark background / silhouette. |
| `overlay_color` | `#ff3b30` | Crack colour in the overlay. |
| `max_alpha` | `0.7` | Max overlay opacity at full confidence. |

## Swapping the model (not model-specific)

Drop a weights file into `./data/crackseg/weights/` on the host (bind-mounted at `/weights`), set `weights: <filename>` in the config, and **Restart** — no rebuild. The loader auto-detects:

- **TorchScript** (`torch.jit.load`) — any architecture, fully self-contained. The portable option.
- A pickled **`nn.Module`** or a **checkpoint** dict with a `model` module.
- A **state_dict** (or `{state_dict: …}`) — loaded into the bundled UNet (set `out_channels` to match).

Match `input_size` / `out_channels` / `crack_index` / `normalize` to your model. `GET /info` (and the console's `/api/crackseg/info`) lists `available_weights`.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness. |
| `GET` | `/info` | `{device, cuda, model_variant, ...config}`. |
| `POST` | `/infer` | Raw image body → RGBA crack-mask PNG sized to the input. |

## Model notes

- The four bundled checkpoints (~62 MB each, one per training loss) are downloaded at build time from the repo's v0.0.1 release. They pickle `crackseg.models.unet.*` instances, so that package is vendored at exactly that path for `torch.load`.
- Runs on CUDA when a GPU is present (compose reserves one), else CPU.
- The frame is resized **preserving aspect** (no squash) and the dark background is suppressed (`ignore_dark`) so detections land on the geometry, not the silhouette.
- **Domain caveat:** the bundled weights are trained on *road* crack imagery (CFD/CrackForest), so they generalise imperfectly to arbitrary 3D renders. For better results on your asset, swap in weights trained for it (see above) or tune `conf_threshold` / `weights`.

## Build + run

```bash
docker compose build crackseg
docker compose up -d crackseg     # or Start it from the console Pipelines page
```
