# rosbag-manager

HTTP API for every bag-plane operation: record start/stop/status, watcher → GCS upload, GCS browser (list / upload / download / delete), and replay via `ros2 bag play`. Binds `127.0.0.1:8086` (loopback only). The `dashboard` service fronts it with HTTP Basic; nothing here is reachable from outside the host.

## Scope

Consumed by `dashboard`, by `scripts/bag-record.sh`, and by any future caller running on the host. Owns the `/data/bags` mount and the GCS client. Does not subscribe to or publish ROS topics directly — `ros2 bag record` / `play` are spawned as subprocesses; they interact with the bus using their own QoS.

## Endpoints

Upload, GCS browser, and replay land in subsequent commits (see HANDOFF open item 3).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness; reports `BAG_DIR` and `GCS_BUCKET`. |
| `POST` | `/api/record/start` | Body `{name?, topics?, duration?}`. Spawns `ros2 bag record` to `${BAG_DIR}/<name>/`. 409 if already recording. `duration` (seconds) auto-stops in the background. |
| `POST` | `/api/record/stop` | SIGTERM the current recording; closes the bag cleanly. 409 if idle. |
| `GET` | `/api/record/status` | `{state, name, topics, output, started_at}` with `state ∈ {idle, recording, stopping}`. |

A per-recording QoS overrides file at `/tmp/qos-<name>.yaml` forces Best Effort on every topic — required for `/mavros/*`, which `ros2 bag record` otherwise misses silently.

## Configuration

| Env | Default | Description |
|---|---|---|
| `BAG_DIR` | `/data/bags` | Local stage for recorded bags before upload. Bind-mounted from `./data/bags`. |
| `GCS_BUCKET` | `atl4s-rosbags` | Target bucket. |
| `ROSBAG_MANAGER_BIND` | `127.0.0.1` | Bind address. Loopback by default. |
| `ROSBAG_MANAGER_PORT` | `8086` | Bind port. |

## Inspecting

```bash
docker compose logs -f rosbag-manager
curl -sS 127.0.0.1:8086/healthz | jq
```

## Credentials

GCS auth via the GCE metadata server (`atl4s-vm-sa` service account); no key file. On the Orin Nano, mount a service-account JSON and set `GOOGLE_APPLICATION_CREDENTIALS=/gcp-key.json`.
