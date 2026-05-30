# inspector

The **backend engine** for the console's 3D-model + rosbag viewer. It has no UI
of its own — the viewer lives in the **console**, which proxies here under
`/api/inspector/*`. Bound to **loopback** (`127.0.0.1:8091`); not browser-facing.
Live defect overlay on the viewed model comes from the separate `crackseg`
service (also console-proxied).

```
console (host :8089)  ──/api/inspector/*──▶  inspector (container, 127.0.0.1:8091)
   three.js viewer                               model store + rosbag delegation
```

## Layout

```
services/inspector/
├── Dockerfile          python:3.11-slim (no frontend, no ROS)
├── entrypoint.sh
└── backend/
    ├── main.py             model upload/list/serve/delete; rosbag list/metadata/play (via rosbag-manager); ML placeholder
    └── config.py
```

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness. |
| `GET` | `/api/models` | List stored models. |
| `POST` | `/api/models` | Multipart upload (`file`); streamed to `MODELS_DIR`. |
| `GET` | `/api/models/{name}/file` | Serve a model (the viewer loads this). |
| `DELETE` | `/api/models/{name}` | Delete a model. |
| `GET` | `/api/rosbags` | List GCS bags (via rosbag-manager). |
| `GET` | `/api/rosbags/{name}/metadata` | Bag metadata: duration, message count, topics. |
| `GET` | `/api/rosbags/status` | Replay status (`idle`/`downloading`/`playing`/`stopping`). |
| `POST` | `/api/rosbags/{name}/play` | Start replaying the bag onto the ROS bus. |
| `POST` | `/api/rosbags/stop` | Stop playback. |
| `GET` | `/api/ml/pipelines` | Placeholder (`supported: false`). |

Filenames are sanitised and resolved within `MODELS_DIR` (no path traversal).
Rosbag endpoints delegate to `rosbag-manager` (`ROSBAG_MANAGER_URL`); only ROS 2
bags (with a `metadata.yaml`) expose metadata / replay — ROS 1 `.bag` files
list but report no metadata.

## Configuration

| Env | Default | Description |
|---|---|---|
| `INSPECTOR_BIND` | `127.0.0.1` | Bind address (loopback; the console proxies to it). |
| `INSPECTOR_PORT` | `8091` | Bind port. |
| `MODELS_DIR` | `/data/models` | Uploaded models (bind-mounted from `./data/models`). |
| `ROSBAG_MANAGER_URL` | `http://127.0.0.1:8086` | rosbag-manager backing the rosbag features. |

## Notes

- Accessed only through the console (dashboard) → **Inspector** page. The console gates every call behind its session auth.
- Containerised (host networking) so it can later take the L4 GPU for ML and reach `rosbag-manager` on `127.0.0.1:8086`. The host console lists/controls this container like any other.
- An FBX/GLB that references **external textures** renders untextured (only the uploaded file is served); embedded-texture models render fully.
- Future: fold `rosbag-manager`'s record/replay/GCS functionality in here so the viewer owns rosbags end-to-end.

## Build + run

```bash
docker compose build inspector
docker compose up -d inspector
# view via the console: http://<VM_external_IP>:8089/  ->  Inspector
```
