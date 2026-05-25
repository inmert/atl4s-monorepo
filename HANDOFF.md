# ATL4S — Handoff

Current state of the project, conventions that aren't obvious from the code, and the next open items.

## Goal

Modular ROS 2 platform for drone telemetry and sensor processing. A Jetson Orin Nano on the drone forwards MAVLink and sensor streams to a GPU-equipped GCP VM that runs the pipeline of independent ROS 2 services in Docker containers (ingestion, perception, fusion, visualization, cloud). Both ends run ROS Humble.

Development is staged: GCP VM first, real drone integration last.

## Architecture

One container per responsibility. ROS topics are the only inter-service interface inside the pipeline; GCP Pub/Sub carries low-rate application events leaving the pipeline.

### Current pipeline

```
ArduPilot SITL ──TCP 5760──▶ MAVProxy ◀──UDP 14550──▶ MAVROS ──ROS topics──▶ commander, foxglove, …
   (atl4s-sitl)                                       (atl4s-mavros)
```

- **SITL** runs `arducopter` (TCP master 5760) plus MAVProxy with `--out udp:127.0.0.1:14550` (bidirectional). Same fan-out pattern is used in production — the Orin runs MAVProxy forwarding to the VM's external IP.
- **MAVROS** binds UDP `0.0.0.0:14550`, uses `apm.launch` (ArduPilot-specific), publishes ~140 topics under `/mavros/*` with **Best Effort** QoS.
- All containers use `network_mode: host` so DDS discovery and same-host UDP work without per-service port maps.
- ROS topics over WAN (drone ↔ VM) will be bridged via Zenoh (`zenoh-bridge-ros2dds`) once Orin sensor topics are in scope. Pure MAVLink from the Orin needs no bridge.

### Key decisions

- **ArduPilot, not PX4.** SITL firmware matches the target drone.
- **MAVROS via `apm.launch`.** ArduPilot-specific entrypoint, not custom MAVLink parsing.
- **Docker Compose with profiles.** `--profile sim` enables SITL; production omits the profile.
- **Host networking everywhere.** No bridge networks, no per-container port maps.
- **Two pub/sub layers.** ROS topics inside the pipeline; GCP Pub/Sub for events leaving the pipeline.
- **Foxglove Studio for visualization.** Browser-based, WebSocket on TCP 8765.
- **Custom messages in `shared/atl4s_msgs/`.** Created when the first service needs one (not yet).

## Repository layout

```
atl4s-monorepo/
├── README.md
├── HANDOFF.md                ← this file
├── docker-compose.yml
├── .env / .env.example
├── docs/                     architecture, deployment, ros-topics
├── services/
│   ├── sitl/                 ArduPilot SITL + MAVProxy fan-out
│   ├── mavros/               MAVLink ⇄ ROS 2 bridge
│   ├── foxglove/             ROS 2 topics → WebSocket on TCP 8765
│   ├── commander/            Autonomy node: telemetry in, MAVROS commands out
│   ├── bag-record/           Records selected topics to mcap (record profile)
│   ├── uploader/             Pushes completed bags to GCS (record profile)
│   └── gazebo/               Gazebo Harmonic + ArduPilot SITL plugin (headless, GPU)
├── shared/
│   └── fastdds_profiles.xml  shared FastDDS XML (see gotchas)
├── data/bags/                (gitignored) local staging area for bags before upload
├── deploy/                   (Terraform, planned)
└── scripts/                  dev-up.sh, prod-up.sh, topic-check.sh,
                              bag-record.sh, bag-list.sh
```

## Infrastructure

| Field | Value |
|---|---|
| GCP project | ATL4S |
| VM | `arachnid-atl4s-vm`, `northamerica-northeast1-c` |
| Machine | g2-standard-8, 1× NVIDIA L4 (24 GB), Ubuntu 22.04, 500 GB SSD |
| External IP | static, reserved |
| Service account | `atl4s-vm-sa` (Storage Object Admin on the bucket only) |
| GCS bucket | `gs://atl4s-rosbags` (us-east4) |
| Access | VS Code Remote-SSH, or MobaXterm |

### Host install state

- NVIDIA driver 595.71.05, CUDA runtime 13.2 (via Google's `cuda_installer.pyz install_driver`).
- ROS 2 Humble on the host (`ros-humble-desktop`, `ros-dev-tools`, `ros-humble-foxglove-bridge`), sourced in `~/.bashrc`.
- Docker (`get.docker.com`) plus NVIDIA Container Toolkit. `docker run --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` verified.
- No CUDA toolkit on the host — CUDA is installed per-container only.

### Firewall (test posture)

`default-allow-ssh` (0.0.0.0/0:22), `default-allow-icmp`, `default-allow-internal`, `allow-foxglove-test` (TCP 8765 from 0.0.0.0/0). IAP / VPN / least-privilege deferred to a later phase.

## Current status

**Telemetry pipeline + Foxglove + commander all working.**

- SITL: stable, GPS lock, EKF converged.
- MAVROS: bound on `0.0.0.0:14550`, link established. `AUTOPILOT_VERSION` round-trip succeeds (proves the bidirectional path).
- Foxglove: listening on `0.0.0.0:8765`, advertising ~140 channels.
- Commander: subscribed to `/mavros/state` and `/mavros/battery`. Verified end-to-end by forcing a trip with `BATTERY_LOW_THRESHOLD=1.0` — commander called `set_mode RTL`, MAVROS accepted, `/mavros/state.mode` reflected `RTL`.

Verify:

```bash
docker exec atl4s-mavros bash -c \
  "source /opt/ros/humble/setup.bash && \
   ros2 topic echo /mavros/state --qos-reliability best_effort --once"
```

Browser: `https://studio.foxglove.dev/` → Open connection → Foxglove WebSocket → `ws://<VM_external_IP>:8765`.

## Conventions and gotchas

### MAVROS URL format

`udp://[bind_host][:bind_port]@[remote_host][:remote_port]` — bind side before the `@`, remote side after.

- `udp://:14550@` — bind on `0.0.0.0:14550`, no remote (learn reply address from the first inbound packet). **What we use.**
- `udp://@:14550` — bind on the default port (14555), treat `:14550` as the remote. Silently breaks ingestion.

Same convention applies to `GCS_URL`.

### MAVROS QoS

Most `/mavros/*` topics are Best Effort. `ros2 topic echo` defaults to Reliable and will silently fail to subscribe — always pass `--qos-reliability best_effort`. `ros2 topic list` and `ros2 topic hz` aren't affected.

### MAVProxy fan-out direction

`--out udp:127.0.0.1:14550` is bidirectional (MAVProxy binds a local ephemeral port and listens for replies on it; MAVROS learns that port from the source address of the first inbound packet). Do not revert to `udpout:` — that is send-only and silently breaks commands from MAVROS to ArduPilot (arm, mode, setpoints) without affecting telemetry. Override at runtime via `MAVPROXY_OUT` in `.env` (no rebuild needed).

### Compose env-anchor merge

Shared env vars live under `x-shared-env: &shared-env` as a **map**, merged into each service's `environment:` (also a map) via `<<: *shared-env`. List-style `environment:` would silently replace the parent's value — YAML's documented behavior. Keep the map form.

### FastDDS shared-memory across containers

FastDDS (Humble's default RMW) prefers SHM when both endpoints look local. Containers with `network_mode: host` share the network namespace but not `/dev/shm`, so DDS discovery (UDP multicast) succeeds while data sent over the SHM locator is silently dropped. Symptom: subscriber sees the topic in `ros2 topic list` and as a matching endpoint in `ros2 topic info -v`, but no messages arrive.

Fix: every ROS container mounts `shared/fastdds_profiles.xml` at `/fastdds_profiles.xml` and sets `FASTRTPS_DEFAULT_PROFILES_FILE` to point at it (wired under `x-common` / `x-shared-env`). The profile disables built-in transports and re-enables UDPv4 only.

Side effect: host-side `ros2` tools need the same env var to see container topics. `export FASTRTPS_DEFAULT_PROFILES_FILE=$PWD/shared/fastdds_profiles.xml`, or run diagnostics inside a container.

### DDS implementation

FastRTPS today (Humble's default). Multi-host with the Orin may benefit from CycloneDDS — install `ros-humble-rmw-cyclonedds-cpp` in both images and set `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` in `x-shared-env` when the time comes.

### Gazebo cosmetic warnings

Two harmless messages on every `atl4s-gazebo` start:

- `Error while loading the library [libGstCameraPlugin.so]: libdebuginfod.so.1: cannot open shared object file` — the gstreamer camera-streaming plugin needs `libdebuginfod1` at runtime. We don't use gstreamer streaming (`ros_gz_bridge` is our path in B.2). Install `libdebuginfod1` in the gazebo image to silence.
- `libEGL warning: egl: failed to create dri2 screen` — Gazebo's EGL backend falls back from DRI2 to the NVIDIA EGL device extension, which works. `nvidia-smi` inside the container shows the GPU in use.

### `ros2 bag record` QoS override YAML

`ros2 bag record` defaults its subscribers to Reliable. To capture `/mavros/*` (Best Effort) you must pass `--qos-profile-overrides-path` with per-topic profiles. The YAML shape Humble's parser accepts is `topic: <dict>`, **not** `topic: [<dict>]` — the more common list form crashes with `'list' object has no attribute 'items'`. `bag-record`'s entrypoint generates the correct shape dynamically from `RECORD_TOPICS`.

### Compose volume merge

Same trap as the env merge above: a service-level `volumes:` list silently replaces `x-common.volumes`. Any service that adds its own volume mounts must re-declare the FastDDS profile mount or lose it. `bag-record` and `uploader` both do this with a one-line comment at the call site.

## Service inventory

| # | Service | Status | Notes |
|---|---|---|---|
| 1 | `mavros` | running | MAVLink ⇄ ROS 2 bridge. |
| 2 | `sitl` | running | ArduPilot SITL + MAVProxy. Only under `--profile sim`. |
| 3 | `foxglove` | running | `ros-humble-foxglove-bridge` on TCP 8765. Image includes `ros-humble-mavros-msgs` so Studio can call MAVROS services. Add the `-msgs` package of every new service that exposes services. |
| 4 | `commander` | running | Autonomy node. Low-battery latch → `set_mode RTL`. Configurable via `BATTERY_LOW_THRESHOLD`. |
| 5 | `bag-record` | running | `ros2 bag record` → mcap under `data/bags/<name>/`. Under `record` profile. Topics via `RECORD_TOPICS`. |
| 6 | `uploader` | running | Polls `data/bags`; uploads completed bags to `gs://atl4s-rosbags`. Idempotent via `<bag>.uploaded` sentinel. Uses VM service account via GCE metadata server. |
| 7 | `gazebo` | running (B.1) | Gazebo Harmonic 8.11 + `ardupilot_gazebo` plugin. Iris quad with gimbal, camera, IMU, GPS in `iris_runway.sdf`. Headless rendering on the L4. ArduPilot SITL plugin listens on UDP 127.0.0.1:9002. |
| 8 | `gz-bridge` | planned (B.2) | `ros_gz_bridge` mapping `/world/iris_runway/.../image`, `imu`, `navsat` → ROS 2 topics under stable names. Adds camera + lidar to `services/sitl` rewrite. |
| 9 | `web-backend` | planned | FastAPI WebSocket service. Subscribes to a curated `/mavros/*` subset (Best Effort). |
| 10 | `web-frontend` | planned | Browser dashboard against `web-backend`. |
| 11 | `bag-replay` | planned | Pulls a bag from GCS and `ros2 bag play`s it onto the DDS bus. |
| 12 | `perception-detector` | planned | Object detection on the L4 GPU. Camera topic available now via Gazebo, real validation when Orin is in scope. |
| 13 | `perception-segmenter` | planned | Segmentation. |
| 14 | `perception-fault` | planned | Fault / anomaly detection. |
| 15 | `perception-lidar` | planned | Point-cloud processing. |
| 16 | `fusion` | planned | Combines perception + pose into tracks / events. |
| 17 | `event-publisher` | planned | Application events → GCP Pub/Sub. |
| 18 | `ingestion` | last | Zenoh bridge for ROS topics over WAN from the Orin. |

## Topic contracts

See [docs/ros-topics.md](docs/ros-topics.md). Stable namespaces:

- `/mavros/*` — managed by MAVROS.
- `/atl4s/*` — reserved for custom ATL4S outputs.
- `/perception/<modality>/<output>` — perception services.
- `/fusion/tracks`, `/atl4s/events` — fusion outputs.

## Open items

1. **`web-backend` + `web-frontend`** — FastAPI WebSocket in `services/web-backend/`, browser dashboard in `services/web-frontend/`.
2. **B.2 — wire Gazebo into the pipeline.** Three pieces: (a) rewrite `services/sitl` so ArduCopter connects to Gazebo's plugin on UDP :9002 instead of running the internal SIM model; (b) add `services/gz-bridge` (`ros_gz_bridge` mapping `/world/iris_runway/.../camera/image` → `/camera/image`, `imu` → `/camera/imu`, `navsat` → `/gps/fix`, plus a 3D lidar once added to `atl4s.sdf`); (c) update `bag-record` defaults to include the new sensor topics; verify a real perception-ready bag in Foxglove.
3. **`bag-replay` service** — pulls a bag from GCS by name and `ros2 bag play`s it onto the DDS bus. Foxglove and commander see it as live data. Pattern: one-shot `docker compose run --rm bag-replay BAG=<name>`.
4. **First perception service** — `shared/atl4s_msgs/` for Detection types, then `services/perception-detector` (CUDA base + YOLO). After B.2 you can validate it against live Gazebo camera frames, not just `image_publisher`.
5. **More `commander` behaviors** — only the low-battery → RTL path exists today. Natural next: takeoff command, waypoint loops, geofence triggers, event publishing to `/atl4s/events`.
6. **Drone integration** — Orin runs MAVProxy with `--out udp:<VM_external_IP>:14550`, open UDP 14550 in the firewall to the Orin's IP. Orin-side `bag-record` + `uploader` push real RealSense + lidar bags to GCS. No downstream changes expected.
7. **Security tightening** — IAP-only SSH (`35.235.240.0/20`), Foxglove / web behind Tailscale, per-team IAM bindings. Defer until test phase is over.
8. **GCS bucket region** — bucket is us-east4 but VM is northamerica-northeast1; consider recreating co-located for production.

## Commands reference

```bash
# Lifecycle
./scripts/dev-up.sh                       # SITL + downstream
./scripts/prod-up.sh                      # no SITL
./scripts/topic-check.sh                  # sanity check
docker compose --profile sim --profile record down  # stop everything

# Record + upload (record profile)
./scripts/bag-record.sh 30                # record 30s, wait for upload
./scripts/bag-list.sh                     # list bags in GCS
docker compose --profile record up -d uploader  # uploader only (e.g. drop bags in by hand)

# Logs
docker compose logs -f
docker compose logs mavros | tail -50

# Process check inside a container
docker exec atl4s-sitl bash -c "ps -ef | grep -E 'arducopter|mavproxy' | grep -v grep"

# Host UDP / TCP bindings (host networking)
sudo ss -lunp | grep -E '14550|5760'
sudo ss -ltnp | grep -E '14550|5760|8765'

# Echo a topic with the right QoS
docker exec atl4s-mavros bash -c \
  "source /opt/ros/humble/setup.bash && \
   ros2 topic echo /mavros/state --qos-reliability best_effort --once"

# Verify in-image entrypoint matches the disk (catches stale rebuilds)
diff <(docker exec atl4s-sitl cat /entrypoint.sh) services/sitl/entrypoint.sh

# Force-clean rebuild (when cached layers cause stale behavior)
docker compose --profile sim --profile record down
docker rmi $(docker images atl4s/* -q)
docker compose --profile sim --profile record build --no-cache
./scripts/dev-up.sh

# VM cost control (~$17/day running, ~$0.07/day stopped)
gcloud compute instances stop  arachnid-atl4s-vm --zone=northamerica-northeast1-c
gcloud compute instances start arachnid-atl4s-vm --zone=northamerica-northeast1-c
```
