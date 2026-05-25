# Architecture

## Service model

Each service runs in a Docker container with a single responsibility. Services communicate only through ROS 2 topics on a shared bus. Custom message types are versioned in `shared/atl4s_msgs/`.

## Why MAVROS

Standard ROS 2 ⇄ MAVLink bridge. Handles the full MAVLink message set, EKF state, ENU/NED frame conversions, and bidirectional command publishing.

## Why ArduPilot SITL

Same firmware as the target drone. PX4 SITL would diverge in parameter names, flight modes, and command semantics, causing mismatches between dev and production. `mavros` uses `apm.launch` (ArduPilot configuration).

## Pub/sub layering

Two distinct mechanisms:

- **ROS topics** — high-rate sensor data inside the pipeline. Sub-millisecond latency, no per-message cost.
- **GCP Pub/Sub** — low-rate application events leaving the pipeline. Durable, fan-out to non-ROS consumers (web backend, alerts, BigQuery).

GCP Pub/Sub is not used for sensor streams (10 MB message limit, ~100 ms latency, per-message billing).

## Orchestration

Docker Compose with profiles. `--profile sim` enables SITL. Production deployment omits the profile, leaving SITL stopped. Services map cleanly to Kubernetes Deployments if horizontal scale is needed later.

## Networking

All containers use `network_mode: host`. DDS discovery and UDP between SITL and MAVROS work without per-service port maps. When the Orin Nano is added, it forwards MAVLink over UDP to the VM's external IP on port 14550. ROS topics over WAN (drone ↔ VM) will be bridged via Zenoh (`zenoh-bridge-ros2dds`) once sensor topics from the Orin are in scope; pure MAVLink telemetry needs no bridge.
