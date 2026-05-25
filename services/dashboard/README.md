# dashboard

Single human-facing surface for ATL4S. React + Vite + TS frontend, FastAPI + rclpy backend, served from one container. HTTP Basic on TCP 8089.

Owns no bag state — proxies every bag-plane action to `rosbag-manager` on `127.0.0.1:8086`. Owns no compute — perception services do inference; the dashboard renders, browses, and triggers. 3D visualisation is deferred to Foxglove Studio via a deep link on the Live and Replay pages; the in-app view is raw data + 2D map + camera.

## Pages

| Path | What it shows |
|---|---|
| `/` | Landing page + tab index. |
| `/live` | Telemetry strip (state, mode, armed, battery, GPS), JPEG camera viewport, per-topic raw-data viewer with rates, "Open in Foxglove ↗" link. |
| `/map` | Leaflet 2D map with OSM tiles, GPS marker + 1000-point trail from `/mavros/global_position/global`. |
| `/bags` | GCS bag list, multipart upload, delete, expandable per-bag panel with parsed `metadata.yaml` (duration, message count, per-topic counts) and file list with download links. |
| `/record` | Start/stop a recording (optional name / topics / duration), live status, local bag table with upload state + force-upload. |
| `/replay` | Bag dropdown, start/stop, status, Foxglove deep link. |
| `/pipelines` | Replay a bag through the perception stack; table of currently-observed `/perception/*` and `/fusion/*` topics (auto-discovered every 5s). |
| `/health` | `DiagnosticArray` from `/atl4s/health` with per-topic level / message / key-value pairs. Aggregate badge in the nav. |

## HTTP + WebSocket surfaces

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness; unauthenticated. |
| `*` | `/api/*` | Streaming proxy to `rosbag-manager` (see [services/rosbag-manager/README.md](../rosbag-manager/README.md)). HTTP Basic at the edge. |
| `WS` | `/ws/topics` | Push curated ROS topic snapshots + rates as JSON deltas. Initial snapshot on connect. |
| `WS` | `/ws/camera` | Push JPEG-encoded `/camera/image` frames as binary WebSocket messages. |
| `GET` | `/`, `/{path}` | Built SPA. SPA fallback for client-side routes (Bags, Live, Map…). |

## Layout

```
services/dashboard/
├── Dockerfile             multi-stage (node build → ros:humble runtime)
├── entrypoint.sh
├── backend/
│   ├── main.py            FastAPI app, lifespan, /healthz, SPA fallback
│   ├── config.py          env-driven config
│   ├── auth.py            HTTP Basic (HTTP + WebSocket via header check)
│   ├── proxy.py           streaming /api/* → rosbag-manager
│   ├── topics.py          rclpy thread → /ws/topics fan-out + auto-discovery
│   └── camera.py          rclpy thread → /ws/camera JPEG fan-out
└── frontend/              React + Vite + TS
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx        nav + routes + health badge
        ├── styles.css
        ├── lib/
        │   ├── api.ts     typed wrappers around /api/*
        │   ├── ws.ts      WebSocket helper with reconnect/backoff
        │   ├── topics.tsx TopicProvider context (single /ws/topics)
        │   ├── format.ts  bytes / dates
        │   └── foxglove.ts deep-link builder
        └── pages/         Home / Live / Map / Bags / Record / Replay / Pipelines / Health
```

## Configuration

| Env | Default | Description |
|---|---|---|
| `DASHBOARD_BIND` | `0.0.0.0` | Bind address. |
| `DASHBOARD_PORT` | `8089` | Bind port. |
| `BAG_WEB_USER` | (unset) | HTTP Basic username. Env-var name kept stable from bag-web for `.env` compatibility. |
| `BAG_WEB_PASS` | (unset) | HTTP Basic password. Both must be set or both unset (auth disabled — only safe behind a closed firewall). |
| `ROSBAG_MANAGER_URL` | `http://127.0.0.1:8086` | Where the proxy layer forwards bag-plane requests. |

## Topic bridge

`backend/topics.py` runs an rclpy executor in a daemon thread and subscribes (Best-Effort QoS to match the publishers) to:

- `/mavros/state`, `/mavros/battery`, `/mavros/imu/data`, `/mavros/global_position/global`
- `/atl4s/health`
- Any topic under `/perception/*` or `/fusion/*` once it appears on the bus (rescan every 5 s via `get_topic_names_and_types()` + dynamic `get_message()`).

Callbacks update an in-memory snapshot and push deltas to per-client `asyncio.Queue`s via `run_coroutine_threadsafe`. The React side mounts `TopicProvider` once at the app root so the nav badge, Live, Map, and Pipelines pages share a single WebSocket.

## Inspecting

```bash
docker compose logs -f dashboard
curl -sS localhost:8089/healthz
curl -sS -u "${BAG_WEB_USER}:${BAG_WEB_PASS}" localhost:8089/api/bags | jq
```

In a browser: open `http://<VM_external_IP>:8089/` — same Basic credentials as the old bag-web service. Open the firewall to port 8089 (e.g. `gcloud compute firewall-rules create allow-dashboard ...`) for external access.

## Development

The Dockerfile builds the frontend in a node:20 stage and copies the result into the runtime image, so iterating on UI code is a `docker compose build dashboard && docker compose up -d --force-recreate dashboard` cycle. For tighter iteration:

```bash
cd services/dashboard/frontend
npm install                      # creates node_modules + lockfile locally
npm run dev                      # vite on :5173 with /api + /ws proxied to :8089
```
