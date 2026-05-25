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

Custom message packages (currently `shared/atl4s_msgs/`) are colcon-built into the image at `/workspace/install/` from the repo-root build context. The entrypoint sources that overlay on top of `/opt/ros/humble/setup.bash`. Without this Studio cannot deserialize `atl4s_msgs/*` topics (e.g. `/perception/lidar/detections`).

## QoS whitelist

`foxglove_bridge` subscribes Reliable + Volatile by default. BE publishers don't match a Reliable sub and get dropped silently. The current entries in [params.yaml](params.yaml) `best_effort_qos_topic_whitelist`:

- `/mavros/.*` — most MAVROS publishers are BE
- `/uas1/.*` — raw MAVLink streams from MAVROS
- `/lidar/.*`, `/perception/.*`, `/fusion/.*` — perception / fusion services publish BE

Add new BE namespaces here when standing up new services. TRANSIENT_LOCAL latched topics (`/tf_static`, `/mavros/home_position/home`, …) are handled automatically by `foxglove_bridge 3.x` durability matching.

## Connecting

In Foxglove Studio: Open connection → Foxglove WebSocket → `ws://<VM_external_IP>:8765`.

GCP firewall rule `allow-foxglove-test` (TCP 8765 from `0.0.0.0/0`) must be in place. Tighten before production.
