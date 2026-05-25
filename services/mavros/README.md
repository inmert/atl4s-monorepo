# mavros

MAVLink ⇄ ROS 2 bridge. Uses `apm.launch` (ArduPilot-specific).

## Output

~50 topics under `/mavros/*`, scoped by our [plugin allowlist](apm_pluginlists.yaml) (vs the upstream ~136 with the default denylist). See [docs/ros-topics.md](../../docs/ros-topics.md) for the curated subset other services depend on, and the "Plugin allowlist" section below for how to add a plugin back.

Most are Best Effort QoS. `ros2 topic echo` defaults to Reliable and will silently fail to subscribe — always pass `--qos-reliability best_effort`:

```bash
ros2 topic echo /mavros/state --qos-reliability best_effort --once
```

`ros2 topic list` and `ros2 topic hz` are unaffected by QoS mismatches. Note that `--qos-reliability` is an `echo`-only flag — passing it to `hz` errors out with "unrecognized arguments"; `hz` subscribes Best Effort by default in Humble so it works without any flag.

## Configuration

| Env | Default | Description |
|---|---|---|
| `FCU_URL` | `udp://:14550@` | MAVLink connection string (see URL format below) |
| `GCS_URL` | (empty) | Optional secondary stream for a GCS |

### URL format

`udp://[bind_host][:bind_port]@[remote_host][:remote_port]` — bind side before the `@`, remote side after.

- `udp://:14550@` — bind on `0.0.0.0:14550`, no remote (learn reply address from the first inbound packet). Use this.
- `udp://@:14550` — binds the default port (14555), treats `:14550` as the remote. Silently breaks ingestion.

## SITL vs. real drone

Configuration is identical. SITL's in-container MAVProxy sends to `127.0.0.1:14550`; the Orin sends to the VM's external IP on `14550`. MAVROS binds `0.0.0.0:14550` either way.

## Plugin allowlist

Upstream `apm.launch` loads ~60 plugins (a denylist of ~10). Most are placeholders for inputs we don't supply (mocap, fake_gps, optical_flow, ADS-B, RTK, …) or features we don't use (log_transfer, mag_calibration, manual_control, …). They publish empty `/mavros/*` topics that clutter the topic graph and slow DDS discovery.

[apm_pluginlists.yaml](apm_pluginlists.yaml) replaces the upstream file with an explicit allowlist of ~18 plugins — every plugin whose data a downstream service consumes today plus the setpoint / waypoint / geofence plugins called out as near-term commander work. The Dockerfile `COPY`s it onto the upstream path; `apm.launch` reads it via `$(find-pkg-share mavros)/launch/apm_pluginlists.yaml` with no extra wiring.

Effect: ~136 `/mavros/*` topics → ~50, ~60 plugin nodes → ~18.

Adding a plugin back later:
1. Add its name to the allowlist in [apm_pluginlists.yaml](apm_pluginlists.yaml).
2. `docker compose build mavros && docker compose up -d --force-recreate mavros`.

Canonical plugin names live in `/opt/ros/humble/share/mavros{,_extras}/mavros_plugins.xml` inside the running container — `docker exec atl4s-mavros bash -c "grep -oE 'name=\"[^\"]+\"' /opt/ros/humble/share/mavros*/mavros_plugins.xml"` enumerates them.
