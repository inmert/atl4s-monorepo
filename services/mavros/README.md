# mavros

MAVLink ⇄ ROS 2 bridge. Uses `apm.launch` for ArduPilot.

## Configuration

| Env | Default | Description |
|---|---|---|
| `FCU_URL` | `udp://@:14550` | MAVLink connection string |
| `GCS_URL` | (empty) | Optional secondary stream for a GCS |

## Outputs

~50 topics under `/mavros/*`. See `docs/ros-topics.md` for the curated subset other services depend on.

## SITL vs. real drone

Configuration is identical. SITL sends MAVLink to UDP 14550 on localhost; the Orin Nano sends to UDP 14550 on this VM's external IP. MAVROS listens on `0.0.0.0:14550` in both cases.
