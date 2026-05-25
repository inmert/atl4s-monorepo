# foxglove

[Foxglove Bridge](https://github.com/foxglove/ros-foxglove-bridge) — exposes ROS 2 topics and services over a WebSocket so [Foxglove Studio](https://studio.foxglove.dev/) can subscribe in a browser.

## Output

| Endpoint | Direction | Consumer |
|---|---|---|
| TCP `0.0.0.0:8765` | listening | Foxglove Studio |

`network_mode: host`, so the port binds on the VM's external interface directly.

## Configuration

| Env | Default | Description |
|---|---|---|
| `FOXGLOVE_PORT` | `8765` | WebSocket port |
| `FOXGLOVE_ADDRESS` | `0.0.0.0` | Bind address |

## Message packages

The image installs `ros-humble-mavros-msgs` so the bridge can expose `/mavros/*` services to Studio. Add the `-msgs` package of every new ATL4S service that exposes services.

## Connecting

In Foxglove Studio: Open connection → Foxglove WebSocket → `ws://<VM_external_IP>:8765`.

GCP firewall rule `allow-foxglove-test` (TCP 8765 from `0.0.0.0/0`) must be in place. Tighten before production.
