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

## Operator UI

The single human-facing surface is the **`console`** — and it **runs on the host**, not in a container, because it manages this very stack (Docker socket, container lifecycle) and must outlive `docker compose down`. It's the `atl4s-console` systemd service on TCP **8089** (FastAPI + React, form-login session auth). It replaced the retired in-container `dashboard`.

The console is the **only browser-facing port**. Heavy backends bind loopback and the console proxies them same-origin (gated by the session cookie):

- **`console`** (host, :8089) — Containers (control + live logs/stats over WS), Deployments (robot/sensor registry), Inspector (three.js 3D-model + rosbag viewer with the `crackseg` defect overlay), Pipelines (start/stop/configure pipeline containers via the Docker socket).
- **`rosbag-manager`** (loopback :8086) — record / watcher+GCS-upload / GCS browser / replay (`ros2 bag play`). Proxied by the console and the Inspector's rosbag controls.
- **`inspector`** (loopback :8091) — stores/serves uploaded 3D models; delegates rosbag ops to `rosbag-manager`. The console serves the three.js viewer.
- **`crackseg`** (loopback :8092, GPU) — surface-defect inference whose mask the Inspector overlays on the model in view.

Foxglove Studio (TCP 8765) stays available for ad-hoc ROS visualisation.
