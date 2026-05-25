# atl4s-monorepo

Modular ROS 2 platform for drone telemetry and sensor processing. A Jetson Orin Nano on the drone forwards MAVLink and sensor streams to a GPU-equipped GCP VM that runs the pipeline of independent ROS 2 services in Docker containers. Both ends run ROS Humble.

## Pipeline

```
ArduPilot SITL ──TCP 5760──▶ MAVProxy ◀──UDP 14550──▶ MAVROS ──ROS topics──▶ commander, foxglove, …
```

In production, SITL is replaced by the Orin Nano forwarding MAVLink over UDP to the VM's external IP on port 14550. MAVROS configuration is identical.

## Layout

```
atl4s-monorepo/
├── README.md
├── HANDOFF.md                ← working context for resuming the project
├── docker-compose.yml
├── .env / .env.example
├── docs/                     architecture, deployment, ros-topics
├── services/
│   ├── sitl/                 ArduPilot SITL + MAVProxy fan-out
│   ├── mavros/               MAVLink ⇄ ROS 2 bridge
│   ├── foxglove/             ROS 2 topics → WebSocket on TCP 8765
│   └── commander/            Autonomy node: telemetry in, MAVROS commands out
├── shared/                   FastDDS XML profile shared by all ROS containers
├── deploy/                   (Terraform, planned)
└── scripts/                  dev-up.sh, prod-up.sh, topic-check.sh
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

See [HANDOFF.md](HANDOFF.md) for the working context and open items.

## Services

| Service | Status | Purpose |
|---|---|---|
| `sitl` | running | ArduPilot SITL + MAVProxy. Only under `--profile sim`. |
| `mavros` | running | MAVLink ⇄ ROS 2 bridge. Always on. |
| `foxglove` | running | Browser visualization via `ros-humble-foxglove-bridge`, TCP 8765. |
| `commander` | running | Autonomy node. Low-battery latch → `set_mode RTL`. |
| `web-backend` | planned | FastAPI WebSocket service for the custom dashboard. |
| `web-frontend` | planned | Browser dashboard. |
| `bag-record` / `bag-replay` | planned | Offline development with recorded data. |
| `perception-detector` | planned | Object detection on the L4 GPU. |
| `perception-segmenter` | planned | Segmentation. |
| `perception-fault` | planned | Fault / anomaly detection. |
| `perception-lidar` | planned | Point-cloud processing. |
| `fusion` | planned | Combines perception + pose into tracks / events. |
| `uploader` | planned | Recorded bags → GCS. |
| `event-publisher` | planned | Application events → GCP Pub/Sub. |
| `ingestion` | planned | Zenoh bridge for ROS topics over WAN from the Orin Nano. |

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
