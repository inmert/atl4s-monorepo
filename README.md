# atl4s-monorepo

Modular ROS 2 platform for drone telemetry and sensor processing. A Jetson Orin Nano on the drone forwards MAVLink and sensor streams to a GPU-equipped GCP VM that runs the pipeline of independent ROS 2 services in Docker containers. Both ends run ROS Humble.

## Pipeline

```
Gazebo Harmonic ◀─UDP 9002 (FDM)─▶ ArduCopter (--model JSON) ──TCP 5760──▶ MAVProxy ◀─UDP 14550─▶ MAVROS ──ROS topics──▶ commander, foxglove, …
       │                              (atl4s-sitl)                                                  (atl4s-mavros)
       │
       └─ camera ──▶ gz-bridge ──▶ ROS 2 topics (/camera/image, /camera/camera_info)
```

In production, Gazebo + the SITL container are replaced by the Orin Nano forwarding MAVLink (from its real ArduPilot autopilot) and the RealSense + lidar topics over UDP/Zenoh. MAVROS configuration is identical.

## Layout

```
atl4s-monorepo/
├── README.md
├── HANDOFF.md                ← working context for resuming the project
├── docker-compose.yml
├── .env / .env.example
├── docs/                     architecture, deployment, ros-topics
├── console/                  Operator dashboard — runs on the HOST (systemd
│                             service atl4s-console, TCP 8089), not a container
├── services/
│   ├── sitl/                 ArduCopter (--model JSON) + MAVProxy fan-out (sim)
│   ├── gazebo/               Gazebo Harmonic + ArduPilot SITL plugin, headless on L4 GPU (sim)
│   ├── gz-bridge/            Maps Gazebo topics → ROS 2 names (sim)
│   ├── mavros/               MAVLink ⇄ ROS 2 bridge
│   ├── foxglove/             ROS 2 topics → WebSocket on TCP 8765
│   ├── commander/            Autonomy node: telemetry in, MAVROS commands out
│   ├── perception-lidar/     DBSCAN lidar detector (3D PointCloud2 or 2D LaserScan input); publishes /perception/lidar/detections + /perception/lidar/markers
│   └── rosbag-manager/       HTTP API for bag-plane ops: record / upload / GCS browser / replay (loopback 127.0.0.1:8086)
├── shared/
│   ├── fastdds_profiles.xml  shared FastDDS XML
│   └── atl4s_msgs/           ament_cmake message package (LidarDetection, LidarDetectionArray)
├── deploy/                   (Terraform, planned)
└── scripts/                  dev-up.sh, prod-up.sh, topic-check.sh,
                              bag-record.sh, bag-list.sh,
                              publish-fake-lidar.sh, publish-fake-scan.sh
```

## Quick start (GCP VM, already provisioned)

```bash
cd ~/atl4s-monorepo
cp .env.example .env       # first time only
./scripts/dev-up.sh        # SITL + downstream
./scripts/topic-check.sh   # confirm /mavros/* topics are visible
docker compose logs -f
```

Verify telemetry (MAVROS publishes Best Effort QoS, so the `--qos-reliability` flag is required):

```bash
docker exec atl4s-mavros bash -c \
  "source /opt/ros/humble/setup.bash && \
   ros2 topic echo /mavros/state --qos-reliability best_effort --once"
```

Expect `connected: true`. Browser: open Foxglove Studio (`https://studio.foxglove.dev/`) → Open connection → Foxglove WebSocket → `ws://<VM_external_IP>:8765`.

Record a bag from the live pipeline (default: 30 s of the four sentinel `/mavros/*` topics; uploads to `gs://atl4s-rosbags` once done):

```bash
./scripts/bag-record.sh 30          # or: ./scripts/bag-record.sh 30 my-bag-name
./scripts/bag-list.sh               # list bags in GCS
```

See [HANDOFF.md](HANDOFF.md) for the working context and open items.

## Services

| Service | Profile | Purpose |
|---|---|---|
| `sitl` | sim | ArduPilot SITL + MAVProxy. |
| `gazebo` | sim | Gazebo Harmonic + ArduPilot SITL plugin. Iris with camera/IMU/GPS, headless on L4. |
| `gz-bridge` | sim | `ros_gz_bridge` mapping Gazebo sensor topics → `/camera/image`, `/camera/camera_info`. Sim-only `/imu/gazebo` and `/clock` are intentionally not bridged (no real-drone analog; production IMU is `/mavros/imu/data`). |
| `mavros` | always | MAVLink ⇄ ROS 2 bridge. |
| `foxglove` | always | Browser visualization via `foxglove_bridge`, TCP 8765. |
| `commander` | always | Autonomy node. Low-battery latch → `set_mode RTL`. |
| `perception-lidar` | always | DBSCAN + per-class shape priors on a configurable lidar input (`/lidar/points` PointCloud2 for 3D, `/lidar/scan` LaserScan for 2D). Publishes `atl4s_msgs/LidarDetectionArray` on `/perception/lidar/detections` and `visualization_msgs/MarkerArray` on `/perception/lidar/markers` for Foxglove Studio's 3D panel. Config from `console/config/pipelines/perception-lidar.yaml`. First user of `shared/atl4s_msgs/`. |
| `rosbag-manager` | always | HTTP API for every bag-plane operation: record start/stop/status, watcher + GCS upload, GCS browser, replay via `ros2 bag play`. Loopback on `127.0.0.1:8086`. Consumed by the console, `scripts/bag-record.sh`, and any future host caller. |
| `perception-detector` | planned | Object detection on the L4 GPU (first GPU service). |
| `perception-segmenter` | planned | Segmentation. |
| `perception-fault` | planned | Fault / anomaly detection. |
| `fusion` | planned | Combines perception + pose into tracks / events. |
| `event-publisher` | planned | Application events → GCP Pub/Sub. |
| `ingestion` | planned | Zenoh bridge for ROS topics over WAN from the Orin Nano. |

## Console (operator dashboard)

The operator UI lives in [`console/`](console/) and runs **natively on the host** as the `atl4s-console` systemd service on TCP **8089** — not a container, since it manages this very stack (Docker socket, container lifecycle). Form login reuses `BAG_WEB_USER` / `BAG_WEB_PASS`. FastAPI backend (`console/api`) + React/Vite frontend (`console/ui`, served from `ui/dist`).

```bash
cd console
./scripts/setup.sh            # build UI (ephemeral node:20) + venv + deps
./scripts/install-service.sh  # install + start the systemd service
# logs: journalctl -u atl4s-console -f   ·   restart: sudo systemctl restart atl4s-console
```

Open `http://<VM_external_IP>:8089/`. See [console/README.md](console/README.md).

## Architecture

One container per responsibility. ROS topics are the only inter-service interface inside the pipeline; GCP Pub/Sub carries low-rate application events leaving the pipeline. All containers use `network_mode: host` for DDS discovery and same-host UDP. ArduPilot on both SITL and the real drone, with MAVROS via `apm.launch`. Custom message packages live in `shared/atl4s_msgs/` once a service needs them. Foxglove Studio is the visualization client.

Full detail in [docs/architecture.md](docs/architecture.md). Topic contracts in [docs/ros-topics.md](docs/ros-topics.md). Provisioning in [docs/deployment.md](docs/deployment.md).

## Infrastructure

| Field | Value |
|---|---|
| GCP project | ATL4S |
| VM | `arachnid-atl4s-vm`, `northamerica-northeast1-c` |
| Machine | g2-standard-8, 1× NVIDIA L4 (24 GB), Ubuntu 22.04, 500 GB SSD |
| GCS bucket | `gs://atl4s-rosbags` (us-east4) |
| External IP | static, reserved |
| Access | VS Code Remote-SSH, or MobaXterm |

Stop the VM when idle (~$17/day running, ~$0.07/day stopped):

```bash
gcloud compute instances stop  arachnid-atl4s-vm --zone=northamerica-northeast1-c
gcloud compute instances start arachnid-atl4s-vm --zone=northamerica-northeast1-c
```
