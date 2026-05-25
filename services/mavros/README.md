# mavros

MAVLink ⇄ ROS 2 bridge. Uses `apm.launch` (ArduPilot-specific).

## Output

~140 topics under `/mavros/*`. See [docs/ros-topics.md](../../docs/ros-topics.md) for the curated subset other services depend on.

Most are Best Effort QoS. `ros2 topic echo` defaults to Reliable and will silently fail to subscribe — always pass `--qos-reliability best_effort`:

```bash
ros2 topic echo /mavros/state --qos-reliability best_effort --once
```

`ros2 topic list` and `ros2 topic hz` are unaffected by QoS mismatches.

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
