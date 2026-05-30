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

MAVROS publishes the topics for the plugins in its allowlist (see [services/mavros/apm_pluginlists.yaml](../services/mavros/apm_pluginlists.yaml)). Run `ros2 topic list` for the full live set and `ros2 topic hz <topic>` to see which are actually publishing (`hz` subscribes Best Effort by default; `echo` needs `--qos-reliability best_effort`).

## Gazebo sensors (gz-bridge, sim profile)

| Topic | Type | Direction | Description |
|---|---|---|---|
| `/camera/image` | `sensor_msgs/Image` | out | RGB frames from the iris gimbal camera (640×480 @ 5 Hz) |
| `/camera/camera_info` | `sensor_msgs/CameraInfo` | out | Intrinsics for `/camera/image` |

Renames are configured in [services/gz-bridge/bridge.yaml](../services/gz-bridge/bridge.yaml). Gazebo-side topic paths include the world name; the ROS-side names stay constant. The Gazebo-side raw IMU (`/world/.../imu_sensor/imu`) and `/world/iris_runway/clock` are intentionally not bridged — sim-only streams with no real-drone analog. Production IMU is `/mavros/imu/data` from ArduPilot, and the pipeline runs on wall-clock.

## Health

There is no dedicated health topic. The dashboard owns health: per-container state via the bind-mounted `/var/run/docker.sock:ro` and per-topic liveness computed from its own topic-bridge timestamps, combined into `GET /api/health` (HTTP Basic). The standalone `services/healthcheck` and its `/atl4s/health` `DiagnosticArray` publisher were retired in phase 4 of the dashboard redesign.

## Perception (lidar — live)

| Topic | Type | Direction | Description |
|---|---|---|---|
| `/lidar/points` | `sensor_msgs/PointCloud2` | in | 3D lidar input. Active when `input_type: pointcloud2` (default). No live source on the VM today; `scripts/publish-fake-lidar.sh` drives synthetic frames at 5 Hz. Real source will come from the Orin via the future `ingestion` service. |
| `/lidar/scan` | `sensor_msgs/LaserScan` | in | 2D planar lidar input. Active when `input_type: laserscan`. `scripts/publish-fake-scan.sh` drives a synthetic 720-ray 360° scan at 5 Hz. |
| `/perception/lidar/detections` | `atl4s_msgs/LidarDetectionArray` | out | Per-frame detections. Each `LidarDetection` carries `class_id` (e.g. "aircraft", "tank", "other"), `score` (0..1), `center` (Point), `size` (Vector3 = length / width / height), `track_id` (int32, 0 when tracking is off). Header frame matches the input message's frame. For 2D LaserScan inputs, `size.z` is always 0. |
| `/perception/lidar/markers` | `visualization_msgs/MarkerArray` | out | Foxglove-ready visualisation of the same detections. Each frame begins with a `DELETEALL` marker (so old detections don't linger), followed by one `CUBE` and one `TEXT_VIEW_FACING` marker per surviving detection. Class is colour-coded (aircraft = orange, tank = red, other = grey). Marker frame matches the detection frame. |

Runtime config lives at `console/config/pipelines/perception-lidar.yaml` (bind-mounted read-only into the container). Lifecycle is controllable from the console; a dedicated Pipelines page is planned.

## Perception (planned)

| Topic | Type | Publisher | Description |
|---|---|---|---|
| `/perception/detections` | `atl4s_msgs/Detection2DArray` | perception-detector | 2D detections in image space |
| `/perception/masks` | `atl4s_msgs/SegmentationMaskArray` | perception-segmenter | Segmentation masks |
| `/perception/faults` | `atl4s_msgs/FaultReport` | perception-fault | Anomaly / fault reports |

## Fusion (planned)

| Topic | Type | Publisher | Description |
|---|---|---|---|
| `/fusion/tracks` | `atl4s_msgs/TrackArray` | fusion | Tracked entities in world frame |
| `/atl4s/events` | `atl4s_msgs/Event` | fusion | Events for downstream consumers |

## Console

The operator dashboard now runs on the host (`console/`, the `atl4s-console` systemd service) and **does not bridge ROS yet** — it talks only to the Docker daemon (Containers page) and its own YAML registries (Deployments). The retired `services/dashboard` container subscribed to ROS via `rclpy` (robot-registry telemetry, dynamic `/perception/*` + `/fusion/*` discovery, on-demand sampling); the console will reintroduce that using the host's `rclpy` when its telemetry pages land. See the NaN/byte JSON gotchas in [HANDOFF.md](../HANDOFF.md) before wiring it.

## rosbag-manager

Sits adjacent to the topic graph — does not subscribe to or publish any ROS topic directly. Spawns `ros2 bag record` and `ros2 bag play` as subprocesses; each child interacts with the bus using its own QoS profile (see the [bag-record QoS gotcha](../HANDOFF.md) for the Best-Effort override file). Replayed bags carry their recorded QoS, so perception services consume them indistinguishably from live data.
