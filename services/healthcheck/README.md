# healthcheck

Periodic topic-liveness monitor for the ATL4S pipeline.

## What it does

Subscribes Best Effort to a tracked set of MAVROS and gz-bridge topics, records last-message timestamps and rolling rates, and exposes the aggregated status on three surfaces:

- **stdout** — one-line summary every `HEALTHCHECK_REPORT_INTERVAL` seconds. Read via `docker compose logs -f healthcheck`.
- **HTTP** — `GET /health` on `HEALTHCHECK_HTTP_PORT` returns JSON + `200 OK` if all topics fresh, `503 Service Unavailable` otherwise. Host networking, so reachable as `http://<VM_external_IP>:8088/health`.
- **ROS topic** — `diagnostic_msgs/DiagnosticArray` on `/atl4s/health`. Foxglove's built-in Diagnostics panel renders it.

## Tracked topics

| Topic | Required | Stale after |
|---|---|---|
| `/mavros/state` | yes | 5 s (also requires `connected: true`) |
| `/mavros/battery` | yes | 5 s |
| `/mavros/global_position/global` | yes | 10 s |
| `/mavros/imu/data` | yes | 3 s |
| `/imu/gazebo` | sim-only | 1 s |
| `/clock` | sim-only | 1 s |
| `/camera/image` | sim-only | 2 s |

A required topic going stale → `ERROR` overall + `503` from HTTP. Sim-only topics going stale → `WARN`, overall stays `OK` (so prod runs without the `sim` profile don't false-fail).

To add a topic, edit `tracked_defaults()` in [healthcheck_node.py](healthcheck_node.py) and rebuild.

## Configuration

| Env | Default | Description |
|---|---|---|
| `HEALTHCHECK_REPORT_INTERVAL` | `5` | Seconds between stdout summary + `/atl4s/health` publish. |
| `HEALTHCHECK_HTTP_PORT` | `8088` | TCP port for `/health` endpoint (host network). |

## Inspecting

```bash
docker compose logs -f healthcheck
curl -sS localhost:8088/health | jq
docker exec atl4s-mavros bash -c \
    "source /opt/ros/humble/setup.bash && \
     ros2 topic echo /atl4s/health --once"
```

## Smoke test

Force an `ERROR` by stopping MAVROS:

```bash
docker compose stop mavros
sleep 6
curl -sSo /dev/null -w "%{http_code}\n" localhost:8088/health   # expect 503
docker compose start mavros
```

`/mavros/state` will go stale, then `connected: false` briefly during MAVROS restart, then return to `OK`.
