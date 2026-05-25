# dashboard

Single human-facing surface for ATL4S. React + Vite + TS frontend (Apple-style sidebar shell, lucide-react icons, design-token CSS with light/dark via `prefers-color-scheme`), FastAPI + rclpy backend, served from one container. HTTP Basic on TCP 8089.

Owns no bag state — proxies every bag-plane action to `rosbag-manager` on `127.0.0.1:8086`. Owns no compute — perception services do inference; the dashboard renders, browses, and triggers. 3D visualisation is deferred to Foxglove Studio via a deep link on the Home, Live, and Replay pages; the in-app view is raw data + 2D map + camera.

Phased Apple-style redesign in progress. Phase 1 (sidebar shell + new IA + design tokens) has shipped; remaining phases listed in `HANDOFF.md` "Open items".

## Pages

| Path | What it shows |
|---|---|
| `/` | Overview. Active-task pill banner (red for record, blue for replay) at the top when either is in flight — click to jump to Rosbag Manager. Stat strip: primary robot's battery / voltage / flight mode + pipelines-running count. Cards for Robots (from `/api/robots`), Health (`/api/health`), Pipelines (`/api/pipelines` — each shows name, in→out topics, status badge), and Rosbags (recent + total with inline recording / replaying indicators). Quick-link tiles to each tab. Foxglove deep link. |
| `/robots` | Device registry from `config/robots.yaml`. Card per robot with kind, live online dot, and one-line state summary. |
| `/robots/:id` | Per-robot detail: telemetry stat strip (state, mode, armed, battery, voltage, lat/lon), Leaflet map scoped to the robot's `gps` topic with 1000-point trail, JPEG camera viewport over `/ws/camera/{robot_id}`, telemetry topic table with rate + last-update, Foxglove deep link. |
| `/pipelines` | YAML-driven perception / fusion service registry (`config/pipelines.yaml`). Card per pipeline with icon, status badge from docker.sock (Running / Stopped / Not deployed), input → output topics, inline Start/Stop, **Run on bag** (modal picker over GCS bags — replays the selected bag onto the bus so the running pipeline consumes it; disabled until the pipeline is Running or while another replay is active), expand-to-Configure drawer. The drawer shows live output rates (sourced from the existing TopicProvider) above a config form generated from the registry's `config_schema`. Field types: `string`, `number`, `slider`, `boolean` (Apple-style toggle), `select` (dropdown), `list_string`. Save persists `config/pipelines/{id}.yaml` atomically; Restart re-execs the container so the service picks up the new values. |
| `/rosbags` | Rosbag Manager — one merged surface. Single table fusing `/api/bags` (GCS) and `/api/uploads` (local stage) on name, sorted newest-first. Per-row "Where" badge: GCS / Local · pending / Uploading / Recording / Replaying. Per-row inline actions are context-aware (Replay / Stop replay / Upload now / Stop recording / Delete). Persistent strip at the top while a record or replay is active, with Stop + Foxglove deep-link. Header buttons: New Recording (modal) + Upload (modal). Expanding a row keeps the metadata.yaml + file-list drawer with download links. Old `/rosbags/{record,replay}` sub-routes still resolve to the same page so saved tabs don't 404. |
| `/ros` | Full ROS topic graph from the rclpy node. Namespace-grouped cards with collapsible sections, type-aware filter, per-topic pub / sub counts. Click a row to open the inspector: per-endpoint node + QoS badge, plus a live sample drawer that opens `/ws/ros/sample/{topic}` and streams the latest message JSON with rate. |
| `/health` | Two cards. **Containers** — every `atl4s-*` container from the host Docker daemon (via mounted `/var/run/docker.sock:ro`) with state, health, uptime, restart count, derived level. **Topic liveness** — per-registry-telemetry-topic age + rate, level OK/IDLE/WARN/ERR. Aggregate badge in the page header and sidebar reflects the worst level (IDLE doesn't degrade — an offline robot in the registry isn't a fault). Combined snapshot at `GET /api/health`. |

## HTTP + WebSocket surfaces

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness; unauthenticated. |
| `GET` | `/api/robots` | List robots from the registry (config + telemetry topic mapping). |
| `GET` | `/api/robots/{id}` | One robot, or 404. |
| `GET` | `/api/ros/topics` | Full topic graph from the rclpy node: every topic on the bus with its types, pub/sub counts, and per-endpoint node name + QoS. The dashboard's own subscriber is filtered out of the sub count. |
| `GET` | `/api/containers` | Per-container state from the host Docker daemon (filtered to the `atl4s-` name prefix). `503` if the docker socket isn't mounted. |
| `GET` | `/api/health` | Combined snapshot: containers + per-topic liveness + aggregate level + per-level counts. Polled by the nav badge / Home card / Health page every 5 s via a single `HealthProvider` context. |
| `GET` | `/api/pipelines` | List of registered pipelines with per-pipeline docker status. |
| `GET` | `/api/pipelines/{id}` | One pipeline + its current on-disk config (schema defaults merged in). |
| `PUT` | `/api/pipelines/{id}/config` | Validate against the schema, persist `config/pipelines/{id}.yaml` atomically. `400` on out-of-range or unknown-select. |
| `POST` | `/api/pipelines/{id}/{start,stop,restart}` | Docker container action. `404` if the container isn't deployed; `409` on docker API conflict (e.g. start an already-running container). |
| `*` | `/api/*` | Streaming proxy to `rosbag-manager` (see [services/rosbag-manager/README.md](../rosbag-manager/README.md)). HTTP Basic at the edge. |
| `WS` | `/ws/topics` | Push curated ROS topic snapshots + rates as JSON deltas. Initial snapshot on connect. |
| `WS` | `/ws/camera/{robot_id}` | Push JPEG-encoded frames from the robot's camera topic as binary WebSocket messages. 4404 close if the robot has no camera configured. |
| `WS` | `/ws/ros/sample/{topic}` | Per-topic sample stream. Opens a transient Best-Effort subscription if not already subscribed; replays the last cached snapshot then streams every message as JSON. 4404 if the topic isn't on the bus or its type can't be resolved. Subscriptions are persistent on the backend (created on first sample, kept open across clients). |
| `GET` | `/`, `/{path}` | Built SPA. SPA fallback for client-side routes. |

## Layout

```
services/dashboard/
├── Dockerfile             multi-stage (node build → ros:humble runtime)
├── entrypoint.sh
├── config/
│   └── robots.yaml        robot registry (bind-mounted, no rebuild)
├── backend/
│   ├── main.py            FastAPI app, lifespan, /healthz, SPA fallback
│   ├── config.py          env-driven config
│   ├── auth.py            HTTP Basic (HTTP + WebSocket via header check)
│   ├── proxy.py           streaming /api/* → rosbag-manager
│   ├── robots.py          registry loader + /api/robots router
│   ├── pipelines.py       registry + per-pipeline config R/W + /api/pipelines/{start,stop,restart,config}
│   ├── ros.py             /api/ros/topics graph endpoint + /ws/ros/sample/{topic} handler
│   ├── containers.py      docker SDK wrapper + /api/containers router (mounts /var/run/docker.sock:ro)
│   ├── health.py          /api/health — combines containers.py + topic-bridge timestamps into one snapshot
│   ├── topics.py          rclpy thread → /ws/topics broadcast + per-topic sample queues; subs from registry + /perception/* /fusion/* discovery + ad-hoc samples
│   └── camera.py          rclpy thread → /ws/camera/{robot_id} JPEG fan-out (one subscription per unique camera topic)
└── frontend/              React + Vite + TS (lucide-react icons)
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx          sidebar shell + routes + health badge
        ├── styles.css       design tokens (light/dark) + component styles
        ├── lib/
        │   ├── api.ts       typed wrappers around /api/* + /api/robots
        │   ├── ws.ts        WebSocket helper with reconnect/backoff
        │   ├── topics.tsx   TopicProvider context (single /ws/topics)
        │   ├── health.tsx   HealthProvider context (polls /api/health every 5s)
        │   ├── robots.ts    iconFor + isOnline / isFresh / summarize helpers
        │   ├── format.ts    bytes / dates
        │   ├── foxglove.ts  deep-link builder
        │   └── components.tsx  PageHeader, Card, StatTile, Badge, StatusDot, EmptyState, Modal, Subnav
        └── pages/           Home / Robots / RobotDetail / Pipelines / RosbagManager / Ros / Health
```

## Configuration

| Env | Default | Description |
|---|---|---|
| `DASHBOARD_BIND` | `0.0.0.0` | Bind address. |
| `DASHBOARD_PORT` | `8089` | Bind port. |
| `BAG_WEB_USER` | (unset) | HTTP Basic username. Env-var name kept stable from bag-web for `.env` compatibility. |
| `BAG_WEB_PASS` | (unset) | HTTP Basic password. Both must be set or both unset (auth disabled — only safe behind a closed firewall). |
| `ROSBAG_MANAGER_URL` | `http://127.0.0.1:8086` | Where the proxy layer forwards bag-plane requests. |
| `ROBOTS_CONFIG` | `/app/config/robots.yaml` | Path to the robot registry YAML (bind-mounted from `services/dashboard/config/` in compose). |
| `PIPELINES_REGISTRY` | `/app/config/pipelines.yaml` | Path to the pipeline registry YAML. |
| `PIPELINES_CONFIG_DIR` | `/app/config/pipelines` | Directory the dashboard writes per-pipeline runtime configs into (one `{id}.yaml` per pipeline). |
| `CONTAINERS_NAME_PREFIX` | `atl4s-` | Substring filter applied to container names when listing for the Health page. Set to empty to surface every container on the host. |

## Robot registry

`config/robots.yaml` lists every robot the dashboard knows about. Each entry:

| Field | Required | Notes |
|---|---|---|
| `id` | yes | kebab-case unique id, used in URLs and the `/ws/camera/{id}` path. |
| `name` | yes | Display name. |
| `kind` | yes | Bucket: `simulator` / `drone` / `rover` / free text. |
| `icon` | yes | Lucide hint: `simulator`, `drone`, `rover`, `bot`. |
| `telemetry.state` | no | `mavros_msgs/State` — drives "Online" + mode/armed. |
| `telemetry.battery` | no | `sensor_msgs/BatteryState` — battery panel. |
| `telemetry.imu` | no | `sensor_msgs/Imu`. |
| `telemetry.gps` | no | `sensor_msgs/NavSatFix` — Leaflet map. |
| `telemetry.camera` | no | `sensor_msgs/Image` — JPEG viewport. |

Online status is derived live in the frontend: a robot is Online when its `state` topic is fresh (`<5 s`) and reports `connected: true`. Robots without a `state` topic fall back to "any telemetry topic seen recently".

Adding a robot:

```bash
$EDITOR services/dashboard/config/robots.yaml      # add entry
docker compose restart dashboard                   # picks up YAML + re-subs topics
```

No rebuild required (the config dir is bind-mounted).

## Topic bridge

`backend/topics.py` runs an rclpy executor in a daemon thread and subscribes (Best-Effort QoS to match the publishers) to:

- `BASE_TOPICS` — `/atl4s/health` only.
- Every telemetry topic referenced by every entry in `config/robots.yaml` (resolved via the `TELEMETRY_TYPES` map: `state` → `mavros_msgs/State`, `battery` → `BatteryState`, `imu` → `Imu`, `gps` → `NavSatFix`). Cameras are handled by the camera bridge instead.
- Any topic under `/perception/*` or `/fusion/*` once it appears on the bus (rescan every 5 s via `get_topic_names_and_types()` + dynamic `get_message()`).

Callbacks update an in-memory snapshot and push deltas to per-client `asyncio.Queue`s via `run_coroutine_threadsafe`. The React side mounts `TopicProvider` once at the app root so the nav badge, Home, Robots, and Pipelines pages share a single WebSocket.

## Camera bridge

`backend/camera.py` opens one `sensor_msgs/Image` subscription per unique `telemetry.camera` topic across the registry, re-encodes each frame to JPEG (quality 70) with OpenCV, and fans out to clients via `/ws/camera/{robot_id}`. The endpoint resolves the robot's camera topic from the registry; a `4404` close means no camera is configured for that robot.

## Pipelines

Two YAML surfaces:

- `config/pipelines.yaml` — the registry. Each entry declares `id`, `name`, `description`, `kind`, `icon`, `container` (docker container name for Start/Stop), `input_topics`, `output_topics`, and a `config_schema` of typed fields.
- `config/pipelines/{id}.yaml` — per-pipeline runtime config. The dashboard reads this on every request (merging on top of the schema defaults so a missing or partial file always produces a complete dict) and writes it on Save. Each perception service is expected to mount the same file and read it at startup.

Field types supported in `config_schema`:

| Type | Renders as | Notes |
|---|---|---|
| `string` | text input | |
| `number` | number input | optional `min`, `max`, `step` |
| `slider` | range slider with live readout | `min`, `max`, `step` required |
| `boolean` | iOS-style toggle | |
| `select` | dropdown | `options:` required |
| `list_string` | comma/whitespace-split text → array | |

Server-side validation rejects out-of-range numbers, unknown select options, and non-list values for `list_string`. Saves are atomic (write to `.yaml.tmp` then `rename`).

Lifecycle (`/api/pipelines/{id}/start|stop|restart`) goes through the same Docker socket the Health page uses. If the container isn't deployed yet, the page shows the pipeline as **Not deployed** (level `idle`, doesn't degrade the aggregate badge) and the action endpoints return `404` with the message "container … is not deployed (build + run the service first)".

Adding a new pipeline:

```bash
$EDITOR services/dashboard/config/pipelines.yaml      # add entry
docker compose restart dashboard                       # picks up registry
# (build + run the service container; it appears as Running once present)
```

## Health (containers + topics)

The dashboard owns health end-to-end — no separate service.

- **Containers** (`backend/containers.py`): `docker.from_env()` talks to the daemon over the bind-mounted `/var/run/docker.sock:ro`. Each `atl4s-*` container's state, health, uptime, restart count, and image are surfaced; severity level is derived from container state (running → ok; restarting/paused → warn; exited/dead → err) and overridden by the container's own health check status if present. `connect()` is called at lifespan startup so a missing socket fails loud.
- **Topic liveness** (`backend/health.py`): per-registry-telemetry-topic, computed off `topics.bridge._timestamps` (no extra ROS subs). Per-key default thresholds match the retired healthcheck service: `state` 5 s, `battery` 5 s, `imu` 3 s, `gps` 10 s, `camera` 5 s. A topic that has never published reports level `idle` rather than `warn` so an offline robot in the registry doesn't degrade the badge. `state` carrying `connected: false` is treated as `warn`.
- **Aggregate**: `level = max(container_levels ∪ topic_levels)` where `idle` is treated as `ok`.

Security note: mounting `/var/run/docker.sock` gives the dashboard container root-equivalent power over the host. Read-only is enough for inspection but the docker daemon doesn't enforce that, so this is acceptable behind HTTP Basic + closed firewall today; flagged for the future security-tightening pass.

## ROS graph + sampling

`backend/ros.py` exposes two surfaces backed by the topic bridge's rclpy node:

- `GET /api/ros/topics` walks the graph via `get_topic_names_and_types()` + `get_publishers/subscriptions_info_by_topic()`. Cheap (graph state is cached locally by the middleware). The dashboard frontend polls this every 5 s on the ROS page.
- `WS /ws/ros/sample/{topic}` opens a per-socket queue routed off the topic bridge's `_on_message`. If the topic isn't already in the bridge's subscription set (i.e. not in the registry's telemetry mappings, not `/atl4s/health`, not a discovered `/perception/*` / `/fusion/*`), the type is resolved from the graph via `rosidl_runtime_py.utilities.get_message()` and a new Best-Effort subscription is created. Subscriptions are persistent — once sampled, the topic is kept subscribed even after the last client leaves. Memory grows once per topic, not per client.

## Inspecting

```bash
docker compose logs -f dashboard
curl -sS localhost:8089/healthz
curl -sS -u "${BAG_WEB_USER}:${BAG_WEB_PASS}" localhost:8089/api/robots | jq
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
