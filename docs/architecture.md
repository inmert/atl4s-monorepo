# Architecture

## Service model

Each service runs in a Docker container with a single responsibility. Services communicate only through ROS 2 topics on a shared bus. Custom message types are versioned in `shared/atl4s_msgs/`.

## Why MAVROS

Standard ROS 2 ⇄ MAVLink bridge. Handles the full MAVLink message set, EKF state, ENU/NED frame conversions, and bidirectional command publishing.

## Why ArduPilot SITL

Same firmware as the target drone. PX4 SITL would diverge in parameter names, flight modes, and command semantics. MAVROS uses `apm.launch` (ArduPilot configuration).

## Pub/sub layering

- **ROS topics** — high-rate sensor data inside the pipeline. Sub-millisecond latency, no per-message cost.
- **GCP Pub/Sub** — low-rate application events leaving the pipeline. Durable, fan-out to non-ROS consumers.

GCP Pub/Sub is not used for sensor streams (10 MB message limit, ~100 ms latency, per-message billing).

## Orchestration

Docker Compose with profiles. `--profile sim` enables SITL; production omits the profile. Services map cleanly to Kubernetes Deployments if horizontal scale is needed later.

## Networking

All containers use `network_mode: host`. DDS discovery and same-host UDP work without per-service port maps. When the Orin Nano is added, it forwards MAVLink to the VM's external IP:14550. ROS topics over WAN will be bridged via Zenoh (`zenoh-bridge-ros2dds`) once sensor topics from the Orin are in scope; pure MAVLink telemetry needs no bridge.

## Operator UI and bag plane

Two services own the human-facing and storage planes; the boundary between them is the bag plane:

- **`dashboard`** — single human-facing surface on TCP 8089 (HTTP Basic). React + Vite + TS frontend + FastAPI/rclpy backend in one container. Streams live ROS topics over `/ws/topics` (curated mavros + atl4s set, with dynamic discovery of `/perception/*` and `/fusion/*`) and JPEG frames over `/ws/camera`. Proxies every bag-plane action to `rosbag-manager` under `/api/*`. Owns no state, runs no models. 3D visualisation is delegated to a Foxglove Studio deep link.
- **`rosbag-manager`** — HTTP API for every bag-plane action: record start/stop/status, watcher + GCS upload, GCS browser (list / files / metadata / download / multipart upload / delete), and replay via `ros2 bag play`. Binds `127.0.0.1:8086` (loopback only; reachable from the dashboard, from `scripts/*`, and from any future service on the host).

This consolidates what would otherwise be six separate services (live backend, browser frontend, bag browser, bag record, bag uploader, bag replay) into two with a clean line: humans hit `dashboard`, bag operations go through `rosbag-manager`. Foxglove Studio stays available for ad-hoc development.
