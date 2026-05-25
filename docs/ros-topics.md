# ROS topic catalogue

Authoritative list of topics other services depend on. Update when a service is added or a contract changes.

## Naming conventions

- `/mavros/*` — managed by MAVROS
- `/atl4s/*` — custom topics from ATL4S services
- `/perception/<modality>/<output>` — perception outputs
- `/fusion/*` — fusion outputs

## Telemetry (mavros, ArduPilot)

| Topic | Type | Direction | Description |
|---|---|---|---|
| `/mavros/state` | `mavros_msgs/State` | out | Connection, armed flag, flight mode |
| `/mavros/battery` | `sensor_msgs/BatteryState` | out | Voltage, current, percentage |
| `/mavros/global_position/global` | `sensor_msgs/NavSatFix` | out | WGS84 lat/lon/alt |
| `/mavros/global_position/local` | `nav_msgs/Odometry` | out | Position relative to home |
| `/mavros/imu/data` | `sensor_msgs/Imu` | out | Orientation, angular velocity, linear accel |
| `/mavros/setpoint_velocity/cmd_vel` | `geometry_msgs/Twist` | in | Velocity commands |
| `/mavros/cmd/arming` (service) | `mavros_msgs/CommandBool` | in | Arm/disarm |
| `/mavros/set_mode` (service) | `mavros_msgs/SetMode` | in | Flight mode change |

MAVROS publishes ~140 topics under `/mavros/*`. Most that aren't listed have no data in default SITL because ArduPilot doesn't stream that message group at the configured rates. Run `ros2 topic list` for the full set and `ros2 topic hz <topic> --qos-reliability best_effort` to see which are actually publishing.

## Gazebo sensors (gz-bridge, sim profile)

| Topic | Type | Direction | Description |
|---|---|---|---|
| `/camera/image` | `sensor_msgs/Image` | out | RGB frames from the iris gimbal camera (640×480 @ 5 Hz) |
| `/camera/camera_info` | `sensor_msgs/CameraInfo` | out | Intrinsics for `/camera/image` |
| `/imu/gazebo` | `sensor_msgs/Imu` | out | Ground-truth IMU (~600 Hz, Best Effort recommended) |
| `/clock` | `rosgraph_msgs/Clock` | out | Sim time (~600 Hz) |

Renames are configured in [services/gz-bridge/bridge.yaml](../services/gz-bridge/bridge.yaml). Gazebo-side topic paths include the world name; the ROS-side names stay constant.

## Health (healthcheck)

| Topic | Type | Direction | Description |
|---|---|---|---|
| `/atl4s/health` | `diagnostic_msgs/DiagnosticArray` | out | Per-tracked-topic freshness (OK/WARN/ERROR) at 0.2 Hz |

Also surfaced as HTTP `GET /health` on TCP 8088 (`200` if all required topics fresh, `503` otherwise).

## Perception (planned)

| Topic | Type | Publisher | Description |
|---|---|---|---|
| `/perception/detections` | `atl4s_msgs/DetectionArray` | perception-detector | 2D detections in image space |
| `/perception/masks` | `atl4s_msgs/SegmentationMaskArray` | perception-segmenter | Segmentation masks |
| `/perception/faults` | `atl4s_msgs/FaultReport` | perception-fault | Anomaly / fault reports |
| `/perception/lidar_objects` | `atl4s_msgs/ObstacleArray` | perception-lidar | Clustered obstacles |

## Fusion (planned)

| Topic | Type | Publisher | Description |
|---|---|---|---|
| `/fusion/tracks` | `atl4s_msgs/TrackArray` | fusion | Tracked entities in world frame |
| `/atl4s/events` | `atl4s_msgs/Event` | fusion | Events for downstream consumers |
