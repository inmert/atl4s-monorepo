# gz-bridge

`ros_gz_bridge` for Gazebo Harmonic ↔ ROS 2 Humble. Maps the long Gazebo topic names produced by the iris model in `services/gazebo` to short stable ROS 2 names that downstream services depend on.

## Mappings

See [bridge.yaml](bridge.yaml). Current contracts:

| Gazebo topic | ROS 2 topic | Type |
|---|---|---|
| `/world/iris_runway/.../camera/image` | `/camera/image` | `sensor_msgs/msg/Image` |
| `/world/iris_runway/.../camera/camera_info` | `/camera/camera_info` | `sensor_msgs/msg/CameraInfo` |
| `/world/iris_runway/.../imu_sensor/imu` | `/imu/gazebo` | `sensor_msgs/msg/Imu` |
| `/world/iris_runway/clock` | `/clock` | `rosgraph_msgs/msg/Clock` |

All currently `GZ_TO_ROS` (one-way). The bridge supports `ROS_TO_GZ` and `BIDIRECTIONAL` for cases like sending commands into Gazebo, which we don't need today (MAVROS handles vehicle commands via the ArduPilot plugin).

## Why stable names

Gazebo topics include the world name and the model path (`/world/iris_runway/model/iris_with_gimbal/...`). If the world or model is swapped, every downstream subscriber breaks. Putting the bridge in between gives us a contract that survives those changes — the world can be replaced with `atl4s.sdf` and only this YAML needs updating.

## Activation

Under the `sim` profile, alongside `gazebo`:

```bash
docker compose --profile sim up -d gz-bridge
```

`depends_on: gazebo` — the bridge will start once the Gazebo container is up, but the actual Gazebo topics may take a few seconds to appear after Gazebo finishes loading the world.
