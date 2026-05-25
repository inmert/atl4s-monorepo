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
| `/lidar/points` | `sensor_msgs/PointCloud2` | in | Lidar input. No live source on the VM today; use `scripts/publish-fake-lidar.sh` to drive synthetic frames at 5 Hz. Real source will come from the Orin via the future `ingestion` service. |
| `/perception/lidar/detections` | `atl4s_msgs/LidarDetectionArray` | out | Per-frame detections. Each `LidarDetection` carries `class_id` (e.g. "aircraft", "tank", "other"), `score` (0..1), `center` (Point), `size` (Vector3 = length / width / height), `track_id` (int32, 0 when tracking is off). Header frame matches the input cloud's frame. |

Configured + lifecycle-controlled from the dashboard Pipelines page. Runtime config lives at `services/dashboard/config/pipelines/perception-lidar.yaml`.

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

## Dashboard

The `dashboard` service is a sink — it subscribes and publishes nothing of its own. Subscriptions come from three sources:

| Source | Topics |
|---|---|
| Robot registry (`services/dashboard/config/robots.yaml`) | Per-robot `state` / `battery` / `imu` / `gps` (telemetry mapping) and `camera` (JPEG fan-out on `/ws/camera/{robot_id}`). Adding a robot to the YAML auto-subscribes its topics on the next dashboard restart. |
| Dynamic discovery (5 s rescan) | Any topic under `/perception/*` or `/fusion/*` whose type can be resolved via `rosidl_runtime_py.utilities.get_message()`. Pipelines page. |
| On-demand sampling | Anything else the user clicks on in the ROS page. The first sample of an unsubscribed topic creates a Best-Effort subscription that's kept open for the process lifetime. |

## rosbag-manager

Sits adjacent to the topic graph — does not subscribe to or publish any ROS topic directly. Spawns `ros2 bag record` and `ros2 bag play` as subprocesses; each child interacts with the bus using its own QoS profile (see the [bag-record QoS gotcha](../HANDOFF.md) for the Best-Effort override file). Replayed bags carry their recorded QoS, so perception services consume them indistinguishably from live data.
