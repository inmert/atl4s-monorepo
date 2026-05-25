# ATL4S — Conversation Handoff

Working-context document for resuming the ATL4S project across sessions. Source of truth for the current state of the pipeline, the immediate next steps, and conventions that aren't obvious from the code. Owner is new to GCP but has general software / Linux familiarity. Works remotely via VS Code Remote-SSH + Claude Code on the GCP VM.

## Project goal

Modular ROS 2 platform for drone telemetry and sensor processing. Jetson Orin Nano on the drone forwards MAVLink and sensor streams (lidar, RealSense, eventually more) to a GPU-equipped GCP VM. The VM runs a pipeline of independent ROS 2 services in Docker containers handling ingestion, perception, fusion, visualization, and cloud integration. Both drone and VM run ROS Humble.

Development is staged: GCP VM first, real drone integration last. Telemetry pipeline is the foundation milestone and is **working** as of the most recent session.

## Architecture

One container per responsibility. ROS topics are the only inter-service interface inside the pipeline; GCP Pub/Sub carries low-rate application events leaving the pipeline. Single-responsibility-per-service is a hard project value; flag designs that drift.

### Current pipeline

```
ArduPilot SITL ──TCP 5760──▶ MAVProxy ◀──UDP 14550──▶ MAVROS ──ROS topics──▶ downstream
   (atl4s-sitl)                                       (atl4s-mavros)
```

- **SITL container** runs `arducopter` (TCP master on 5760) plus MAVProxy with `--out udp:127.0.0.1:14550` (bidirectional: MAVProxy sends from a local ephemeral port and listens for replies on it, so MAVROS commands round-trip back). Same fan-out pattern is used in production — the Orin Nano runs MAVProxy forwarding to the VM's external IP.
- **MAVROS container** binds UDP `0.0.0.0:14550`, uses `apm.launch` (ArduPilot-specific), publishes ~50 topics under `/mavros/*` with **Best Effort** QoS.
- Both containers use `network_mode: host` so DDS discovery and same-host UDP work without per-service port maps.
- ROS topics over WAN (drone ↔ VM) will be bridged via Zenoh (`zenoh-bridge-ros2dds`) once Orin sensor topics are in scope. Pure MAVLink telemetry from the Orin needs no bridge.

### Key architectural decisions

- **ArduPilot, not PX4.** SITL firmware matches the target drone to avoid divergence in parameters, modes, and command semantics.
- **MAVROS, not custom MAVLink parsing.** `apm.launch` is the ArduPilot-specific entrypoint.
- **Docker Compose with profiles.** `--profile sim` enables SITL; production omits the profile.
- **Host networking everywhere.** No bridge networks; no per-container port maps.
- **Two pub/sub layers.** ROS topics inside the pipeline (high-rate, in-process latency). GCP Pub/Sub for events leaving the pipeline (durable, fan-out to non-ROS consumers).
- **Foxglove Studio for visualization.** Browser-based, WebSocket on TCP 8765.
- **Custom messages in `shared/atl4s_msgs/`.** Not created yet — added when the first service needs a custom type.

## Repository layout

```
atl4s-monorepo/
├── README.md
├── HANDOFF.md              ← this file
├── docker-compose.yml
├── .env / .env.example
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   └── ros-topics.md
├── services/
│   ├── sitl/               Dockerfile, entrypoint.sh, README.md
│   └── mavros/             Dockerfile, entrypoint.sh, README.md
├── shared/                 (custom message packages, created on demand)
├── deploy/                 (Terraform, planned)
└── scripts/
    ├── dev-up.sh           SITL + downstream
    ├── prod-up.sh          real drone + downstream (no SITL)
    └── topic-check.sh      sanity-check expected topics exist
```

## Infrastructure

| Field | Value |
|---|---|
| GCP project | ATL4S |
| VM name | `arachnid-atl4s-vm` |
| Zone | `northamerica-northeast1-c` |
| Machine type | g2-standard-8 |
| GPU | 1× NVIDIA L4 (24 GB) |
| OS | Ubuntu 22.04 LTS |
| Disk | 500 GB SSD persistent |
| External IP | static, reserved |
| Service account | `atl4s-vm-sa` (Storage Object Admin on the bucket only) |
| GCS bucket | `gs://atl4s-rosbags` (us-east4) |
| User | `arachnid` |
| Access | VS Code Remote-SSH + Claude Code, or MobaXterm |

### Host installation state

- NVIDIA driver 595.71.05, CUDA runtime 13.2 (installed via Google's `cuda_installer.pyz install_driver`).
- ROS 2 Humble installed on the host directly (`ros-humble-desktop`, `ros-dev-tools`, `ros-humble-foxglove-bridge`), sourced in `~/.bashrc`.
- Docker (`get.docker.com`) plus NVIDIA Container Toolkit. `docker run --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` verified.
- `python3-pip`, `colcon`, `tmux`, `htop`, `nvtop` installed.
- No CUDA toolkit on the host — CUDA is installed per-container only.

### Firewall (test posture)

`default-allow-ssh` (0.0.0.0/0:22), `default-allow-icmp`, `default-allow-internal`, `default-allow-rdp` (unused), `allow-foxglove-test` (TCP 8765 from 0.0.0.0/0). IAP / VPN / least-privilege firewall deferred to a later phase by explicit choice.

## Current status

**Telemetry pipeline + Foxglove bridge are working.**

- SITL container: stable, GPS lock, EKF converged.
- MAVROS container: bound on `0.0.0.0:14550`, all plugins loaded, link to the autopilot established. `AUTOPILOT_VERSION` round-trip succeeds (proves the bidirectional path through MAVProxy).
- Foxglove container: listening on `0.0.0.0:8765`, advertising ~140 channels for every `/mavros/*` topic plus the MAVROS services (arming, set_mode, param, etc.).
- `/mavros/state` reports `connected: true`, current flight mode (`STABILIZE` at idle).
- `/mavros/battery` reports voltage, percentage, and per-cell voltages.
- `./scripts/topic-check.sh` should report OK for the four sentinel topics.

Verify with:

```bash
docker exec atl4s-mavros bash -c \
  "source /opt/ros/humble/setup.bash && \
   ros2 topic echo /mavros/state --qos-reliability best_effort --once"
```

To inspect live in a browser: open `https://studio.foxglove.dev/` → "Open connection" → "Foxglove WebSocket" → `ws://<VM_external_IP>:8765`.

## Conventions and gotchas

These are non-obvious and worth keeping in front of mind.

### MAVROS URL format

`udp://[bind_host][:bind_port]@[remote_host][:remote_port]` — bind side is **before** the `@`, remote side is **after**.

- `udp://:14550@` — bind on `0.0.0.0:14550`, no remote (learn reply address from first inbound packet). **This is what we use.**
- `udp://@:14550` — bind on the default port (14555), treat `:14550` as the remote. Silently breaks ingestion if MAVProxy sends to 14550 and nothing is listening there.

Same convention applies to `GCS_URL`.

### MAVROS QoS

Most MAVROS topics are published with **Best Effort** reliability. `ros2 topic echo` defaults to **Reliable** and will subscribe with no matching publisher. Always pass `--qos-reliability best_effort` when echoing `/mavros/*` topics. `ros2 topic list` and `ros2 topic hz` are not affected.

### MAVProxy fan-out direction

`--out udp:127.0.0.1:14550` (bidirectional). MAVProxy binds a local ephemeral port, sends from it to MAVROS, and listens for replies on the same port. MAVROS learns that ephemeral port from the source address of the first inbound packet. Do **not** revert to `udpout:` — that is send-only and silently breaks commands from MAVROS to ArduPilot (arm, mode change, setpoints) without affecting telemetry. The runtime value can be overridden via the `MAVPROXY_OUT` env var in `.env` without rebuilding the SITL image.

### Stale entrypoint risk

The on-disk `services/sitl/entrypoint.sh` and the entrypoint baked into the running image were briefly out of sync in May 2026 (disk had `exec mavproxy.py --daemon`, image had the working background + `wait -n` version). If a rebuild ever brings back `--daemon`, the container will restart-loop because MAVProxy daemonizes and PID 1 exits. The committed version is the working one — verify with:

```bash
diff <(docker exec atl4s-sitl cat /entrypoint.sh) services/sitl/entrypoint.sh
```

### Compose env-anchor merge

Shared env vars live under `x-shared-env: &shared-env` as a **map**, merged into each service's `environment:` (also a map) via `<<: *shared-env`. List-style `environment:` would silently replace the parent's value — this is YAML's documented behavior, not a Compose bug. Keep the map form when adding shared env vars.

### FastDDS shared-memory transport across containers

FastDDS (the Humble default RMW) prefers shared memory for data delivery when both endpoints look local. Containers with `network_mode: host` share the network namespace but **not** `/dev/shm`, so DDS discovery (UDP multicast) works while data sent over the SHM locator is silently dropped. Symptom: a subscriber sees the topic in `ros2 topic list` and `ros2 topic info -v` shows it as a matching endpoint, but no messages arrive.

Fix in this repo: every ROS container mounts `shared/fastdds_profiles.xml` at `/fastdds_profiles.xml` and sets `FASTRTPS_DEFAULT_PROFILES_FILE` to point at it (both wired in `docker-compose.yml` under `x-common` / `x-shared-env`). The profile disables built-in transports and re-enables UDPv4 only.

Side effect: tools running on the **host** (`ros2 topic echo` from a host shell) need the same env var set to see container topics — they have their own `/dev/shm` too. Either `export FASTRTPS_DEFAULT_PROFILES_FILE=$PWD/shared/fastdds_profiles.xml` or run diagnostics inside a container.

### DDS implementation

Both images use the ROS 2 default RMW (FastRTPS). Sufficient for single-host. Multi-host with the Orin Nano may benefit from CycloneDDS for tunable QoS / discovery — install `ros-humble-rmw-cyclonedds-cpp` in both images and set `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` in `x-shared-env` when the time comes.

## Service inventory and priority

| # | Service | Status | Notes |
|---|---|---|---|
| 1 | `mavros` | running | MAVLink ⇄ ROS 2 bridge |
| 2 | `sitl` | running | ArduPilot SITL + MAVProxy. Only under `--profile sim`. |
| 3 | `foxglove` | running | `ros-humble-foxglove-bridge` on TCP 8765. Image includes `ros-humble-mavros-msgs` so Studio can call MAVROS services (arming, set_mode, params). Add the `-msgs` package of every new service that exposes services. |
| 4 | `web-backend` | planned | FastAPI WebSocket service. Subscribes to curated `/mavros/*` subset with Best Effort QoS. |
| 5 | `web-frontend` | planned | Browser dashboard against `web-backend` |
| 6 | `commander` | planned | Subscribes to telemetry, publishes setpoints. Requires bidirectional MAVProxy (see gotcha above). |
| 7 | `bag-record` / `bag-replay` | planned | Offline development with recorded data |
| 8 | `perception-detector` | planned | Object detection on L4 GPU |
| 9 | `perception-segmenter` | planned | Segmentation |
| 10 | `perception-fault` | planned | Fault / anomaly detection |
| 11 | `perception-lidar` | planned | Point-cloud processing |
| 12 | `fusion` | planned | Combines perception + pose into tracks / events |
| 13 | `uploader` | planned | Recorded bags → GCS |
| 14 | `event-publisher` | planned | Application events → GCP Pub/Sub |
| 15 | `ingestion` | last | Zenoh bridge for ROS topics over WAN from the Orin Nano |

## Topic contracts

See [docs/ros-topics.md](docs/ros-topics.md). Stable namespaces:

- `/mavros/*` — managed by MAVROS, ~50 topics. Curated subset in the doc.
- `/atl4s/*` — reserved for custom ATL4S service outputs.
- `/perception/<modality>/<output>` — perception services.
- `/fusion/tracks`, `/atl4s/events` — fusion outputs.

## Open items

1. **`commander` service** — start with a trivial behavior (e.g. "log a warning when battery < 20 %", then expand to "RTL when battery < 20 %"). Pattern: subscribe Best Effort, publish to `/mavros/setpoint_velocity/cmd_vel` or call `/mavros/cmd/arming` service.
2. **`web-backend` + `web-frontend`** — FastAPI WebSocket service in `services/web-backend/`, plain HTML / JS or React in `services/web-frontend/`. Both behind nginx or directly exposed.
3. **Drone integration** — when the Orin is ready, set `FCU_URL=udp://:14550@` on the VM (already the value), have the Orin run MAVProxy with `--out udp:<VM_external_IP>:14550`, open UDP 14550 to the Orin's IP in the firewall. No downstream changes expected.
4. **Security tightening** — replace `default-allow-ssh` with IAP-only SSH (`35.235.240.0/20`), move Foxglove / web traffic behind Tailscale or similar, add per-team-member IAM bindings. Defer until test phase is over.
5. **GCS bucket region** — bucket is in us-east4; VM is in northamerica-northeast1. Functional but slightly slower transfers. Consider recreating in northamerica-northeast1 for production.

## Owner preferences

- Concise, professional documentation. Owner has previously flagged AI-generated or marketing-style prose (`powerful`, `seamless`, `robust`, excessive bullet hierarchies). Avoid.
- Step-by-step instructions with exact commands, not descriptions of commands.
- Brief "why" with each recommendation — one short sentence is the target.
- Modularity is a core value. Push back on designs that bundle responsibilities into a single container or service.

## Commands reference

### Lifecycle

```bash
# Bring up dev pipeline (SITL + downstream)
cd ~/atl4s-monorepo && ./scripts/dev-up.sh

# Bring up prod pipeline (no SITL)
cd ~/atl4s-monorepo && ./scripts/prod-up.sh

# Stop everything
docker compose --profile sim down

# Sanity check
./scripts/topic-check.sh
```

### Inspection

```bash
# Live logs
docker compose logs -f
docker compose logs mavros | tail -50

# Process check inside a container
docker exec atl4s-sitl bash -c "ps -ef | grep -E 'arducopter|mavproxy' | grep -v grep"

# Host UDP / TCP bindings (both containers use host networking)
sudo ss -lunp | grep -E '14550|5760'
sudo ss -ltnp | grep -E '14550|5760'

# Echo a topic with the right QoS
docker exec atl4s-mavros bash -c \
  "source /opt/ros/humble/setup.bash && \
   ros2 topic echo /mavros/state --qos-reliability best_effort --once"

# Verify entrypoint inside the image matches the disk
diff <(docker exec atl4s-sitl cat /entrypoint.sh) services/sitl/entrypoint.sh
```

### Rebuild (when cached layers cause stale behavior)

```bash
docker compose --profile sim down
docker rmi atl4s/sitl:latest atl4s/mavros:latest
docker compose --profile sim build --no-cache sitl mavros
./scripts/dev-up.sh
```

### VM cost control

```bash
gcloud compute instances stop arachnid-atl4s-vm --zone=northamerica-northeast1-c
gcloud compute instances start arachnid-atl4s-vm --zone=northamerica-northeast1-c
```

Running cost ~$17/day on-demand; stopped cost ~$0.07/day (disk only).
