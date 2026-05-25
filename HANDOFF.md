# ATL4S — Handoff

Current state of the project, conventions that aren't obvious from the code, and the next open items.

## Goal

Modular ROS 2 platform for drone telemetry and sensor processing. A Jetson Orin Nano on the drone forwards MAVLink and sensor streams to a GPU-equipped GCP VM that runs the pipeline of independent ROS 2 services in Docker containers (ingestion, perception, fusion, visualization, cloud). Both ends run ROS Humble.

Development is staged: GCP VM first, real drone integration last.

## Architecture

One container per responsibility. ROS topics are the only inter-service interface inside the pipeline; GCP Pub/Sub carries low-rate application events leaving the pipeline.

### Current pipeline

```
Gazebo Harmonic ◀─UDP 9002 (FDM)─▶ ArduCopter ──TCP 5760──▶ MAVProxy ◀─UDP 14550─▶ MAVROS ──ROS topics──▶ commander, foxglove, …
  (atl4s-gazebo)                  (--model JSON,                                  (atl4s-mavros)
                                   atl4s-sitl)
       │
       └─ camera/imu/clock ─▶ gz-bridge ─▶ /camera/image, /imu/gazebo, /clock
                              (atl4s-gz-bridge)
```

- **Gazebo** runs `iris_runway.sdf` headless on the L4 GPU with the `ardupilot_gazebo` plugin loaded. Plugin listens on UDP 127.0.0.1:9002 for the JSON FDM stream.
- **SITL** runs `arducopter --model JSON --defaults copter.parm,gazebo-iris.parm`. Sensors (IMU, GPS, baro) come from Gazebo over JSON FDM. MAVLink still exposed on TCP 5760, fan-out to MAVROS unchanged via MAVProxy `--out udp:127.0.0.1:14550` (bidirectional).
- **gz-bridge** runs `ros_gz_bridge parameter_bridge` with a YAML config that renames the long Gazebo topic paths to short stable ROS 2 names. One-way (GZ_TO_ROS); MAVROS handles all commands into the vehicle.
- **MAVROS** binds UDP `0.0.0.0:14550`, uses `apm.launch`, publishes ~140 topics under `/mavros/*` with **Best Effort** QoS.
- All containers use `network_mode: host` so DDS discovery and same-host UDP work without per-service port maps.
- ROS topics over WAN (drone ↔ VM) will be bridged via Zenoh (`zenoh-bridge-ros2dds`) once Orin sensor topics are in scope.

### Key decisions

- **ArduPilot, not PX4.** SITL firmware matches the target drone.
- **MAVROS via `apm.launch`.** ArduPilot-specific entrypoint, not custom MAVLink parsing.
- **Docker Compose with profiles.** `--profile sim` enables SITL; production omits the profile.
- **Host networking everywhere.** No bridge networks, no per-container port maps.
- **Two pub/sub layers.** ROS topics inside the pipeline; GCP Pub/Sub for events leaving the pipeline.
- **Foxglove Studio for visualization.** Browser-based, WebSocket on TCP 8765.
- **`diagnostic_msgs/DiagnosticArray` for health.** Standard ROS type instead of standing up `shared/atl4s_msgs/` early; Foxglove's Diagnostics panel renders it directly.
- **Custom messages in `shared/atl4s_msgs/`.** Created when the first perception service needs one (not yet).

## Repository layout

```
atl4s-monorepo/
├── README.md
├── HANDOFF.md                ← this file
├── docker-compose.yml
├── .env / .env.example
├── docs/                     architecture, deployment, ros-topics
├── services/
│   ├── sitl/                 ArduPilot SITL + MAVProxy fan-out (sim profile)
│   ├── gazebo/               Gazebo Harmonic + ArduPilot SITL plugin (sim profile, headless GPU)
│   ├── gz-bridge/            Gazebo topics → ROS 2 names (sim profile)
│   ├── mavros/               MAVLink ⇄ ROS 2 bridge
│   ├── foxglove/             ROS 2 topics → WebSocket on TCP 8765
│   ├── commander/            Autonomy node: telemetry in, MAVROS commands out
│   ├── healthcheck/          Topic-liveness monitor; stdout + HTTP /health + /atl4s/health
│   ├── dashboard/            Operator UI: live view, bags, record/replay, pipelines, health (HTTP Basic, TCP 8089)
│   └── rosbag-manager/       HTTP API for bag-plane ops: record / upload / GCS browser / replay (loopback 127.0.0.1:8086)
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

**Full pipeline working with Gazebo as the simulator.**

- Gazebo Harmonic 8.11 rendering on L4 GPU, iris_with_gimbal model in `iris_runway.sdf`.
- SITL: `arducopter --model JSON` connected to Gazebo's FDM bridge on UDP 9002. 1413 params synced, EKF3 IMU0/1 initialised and tilt-aligned, `ArduPilot Ready`. MAVProxy `--streamrate 10` (was the default 4 → topic rates were ~2 Hz).
- MAVROS: bound on `0.0.0.0:14550`, link established. `/mavros/*` sensor topics at ~5 Hz (capped by ArduPilot below the requested 10).
- gz-bridge: `/camera/image` (640×480 @ 5 Hz), `/camera/camera_info`, `/imu/gazebo` (~600 Hz), `/clock` (~600 Hz) flowing as ROS 2 topics.
- Foxglove: WebSocket on `0.0.0.0:8765`. BE whitelist covers `/imu/gazebo`, `/clock`, `/mavros/.*`, `/uas1/.*` (raw MAVLink dropped silently without the last one).
- Commander: low-battery → `set_mode RTL` verified end-to-end (forced via `BATTERY_LOW_THRESHOLD=1.0`).
- Healthcheck: tracks 7 topics, reports stdout summary every 5 s, HTTP `GET /health` on `:8088` (200/503), publishes `/atl4s/health` (DiagnosticArray) for Foxglove.
- rosbag-manager: HTTP API on `127.0.0.1:8086` for record / upload / GCS browser / replay. Smoke tested end-to-end via `./scripts/bag-record.sh` — record subprocess + watcher upload + GCS confirmed; replay downloads from GCS, plays, and cleans up `${REPLAY_DIR}`.
- dashboard: operator UI on `:8089` with HTTP Basic via `BAG_WEB_USER` / `BAG_WEB_PASS`. Pages: Home, Live (telemetry + camera + raw-data viewer), Map (Leaflet GPS plot), Bags (browser + metadata + multipart upload + delete), Record, Replay, Pipelines (auto-discovers `/perception/*` and `/fusion/*` every 5 s), Health (DiagnosticArray + nav badge). All `/api/*` calls stream-proxy to `rosbag-manager`; `/ws/topics` and `/ws/camera` bridge rclpy subscribers from a daemon thread. Foxglove Studio deep link on Live and Replay.

Verify:

```bash
# MAVROS link
docker exec atl4s-mavros bash -c \
  "source /opt/ros/humble/setup.bash && \
   ros2 topic echo /mavros/state --qos-reliability best_effort --once"

# Pipeline liveness
curl -sS localhost:8088/health | jq .status        # OK if all required topics fresh

# dashboard (auth from .env)
curl -sS -u "${BAG_WEB_USER}:${BAG_WEB_PASS}" localhost:8089/api/bags | jq
```

Browser: `https://studio.foxglove.dev/` → Open connection → Foxglove WebSocket → `ws://<VM_external_IP>:8765`. Bag UI at `http://<VM_external_IP>:8089/`.

## Conventions and gotchas

### MAVROS URL format

`udp://[bind_host][:bind_port]@[remote_host][:remote_port]` — bind side before the `@`, remote side after.

- `udp://:14550@` — bind on `0.0.0.0:14550`, no remote (learn reply address from the first inbound packet). **What we use.**
- `udp://@:14550` — bind on the default port (14555), treat `:14550` as the remote. Silently breaks ingestion.

Same convention applies to `GCS_URL`.

### MAVROS QoS

Most `/mavros/*` topics are Best Effort. `ros2 topic echo` defaults to Reliable and will silently fail to subscribe — always pass `--qos-reliability best_effort`. `ros2 topic list` and `ros2 topic hz` aren't affected.

### Foxglove subscription QoS

Foxglove Bridge subscribes Reliable + Volatile by default. Two failure modes:

1. **BE publisher + Reliable sub → no data.** Fix via the `best_effort_qos_topic_whitelist` regex list in [services/foxglove/params.yaml](services/foxglove/params.yaml). Current entries: `/imu/gazebo`, `/clock`, `/mavros/.*`, `/uas1/.*`. Add new BE namespaces here when you create services.
2. **TRANSIENT_LOCAL publisher + Volatile sub → latched message missed.** Affects `/tf_static`, `/mavros/home_position/home`, `/mavros/mission/*`, `/mavros/global_position/gp_origin`. They appear "stuck waiting for next message" in Foxglove panels because the latched value was sent before the sub joined. `foxglove_bridge 3.x` auto-matches durability when it sees the publisher's QoS, so this is usually fine in practice — but if a specific latched topic is empty in Foxglove, this is why.

### MAVProxy stream rate

ArduCopter 4.8 removed the `SR0_*` per-channel stream-rate params for SERIAL0 (the channel SITL uses). MAVProxy is now the only knob — set `MAVPROXY_STREAMRATE` (default 10 Hz) which becomes `mavproxy.py --streamrate <n>`. ArduPilot rate-limits below the requested value (observed ~5 Hz on `/mavros/imu/data`, `/mavros/global_position/*`, etc.). Don't waste time looking for `SR0_*` in `mav.parm` — only `MAV1_*`/`MAV2_*`/`MAV3_*` exist, and all read 0 for SERIAL0.

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

### Gazebo battery → ArduCopter failsafe on first boot

ArduCopter logs `Flight battery warning` and triggers `RTL` briefly on every SITL startup. The Gazebo battery sim reports a momentarily low value during sensor initialisation; ArduCopter's internal battery failsafe (separate from our `commander`) fires before the value settles to 12.6 V. This is not a `commander` action and is harmless — mode flips back to STABILIZE once the battery reads normally. If it becomes a problem (e.g. it fires during a real autonomous mission), the fix is parameter-level (`BATT_LOW_VOLT`, `BATT_FS_LOW_ACT`) in `gazebo-iris.parm`.

### Gazebo cosmetic warnings

Two harmless messages on every `atl4s-gazebo` start:

- `Error while loading the library [libGstCameraPlugin.so]: libdebuginfod.so.1: cannot open shared object file` — the gstreamer camera-streaming plugin needs `libdebuginfod1` at runtime. We use `ros_gz_bridge` instead. Install `libdebuginfod1` in the gazebo image to silence.
- `libEGL warning: egl: failed to create dri2 screen` — Gazebo's EGL backend falls back from DRI2 to the NVIDIA EGL device extension, which works. `nvidia-smi` inside the container shows the GPU in use.

### `ros2 bag record` QoS override YAML

`ros2 bag record` defaults its subscribers to Reliable. To capture `/mavros/*` (Best Effort) you must pass `--qos-profile-overrides-path` with per-topic profiles. The YAML shape Humble's parser accepts is `topic: <dict>`, **not** `topic: [<dict>]` — the more common list form crashes with `'list' object has no attribute 'items'`. `rosbag-manager` (`app/record.py`) generates the correct shape per recording from the request's `topics` list.

### Compose volume merge

Same trap as the env merge above: a service-level `volumes:` list silently replaces `x-common.volumes`. Any service that adds its own volume mounts must re-declare the FastDDS profile mount or lose it. `rosbag-manager` does this with a one-line comment at the call site.

### ROS `byte` field → 1-char string in JSON

`rosidl_runtime_py.message_to_ordereddict()` represents ROS `byte` fields as 1-character `str`, not `int`. `diagnostic_msgs/DiagnosticStatus.level` is the obvious one (`b'\x00'` becomes `" "` in the JSON the dashboard ships to the browser). The dashboard frontend coerces via `String.charCodeAt(0)` in `pages/Health.tsx` and `App.tsx`. Other byte fields to watch for if they ever surface: `sensor_msgs/BatteryState.power_supply_status`, `sensor_msgs/Imu` orientation_covariance (no, that's float).

### HTTP Basic auth across WebSocket upgrades

The dashboard reuses `BAG_WEB_USER` / `BAG_WEB_PASS` as the realm for both `/api/*` (HTTP) and `/ws/*` (WebSocket). Browsers cache Basic credentials per origin and resend them on the WebSocket upgrade request — `backend/auth.py:check_websocket()` reads the cached `Authorization: Basic ...` header. The cache only populates after the user has authenticated for a normal HTTP request first, so open the SPA root before any direct `/ws/*` test from a browser.

### Dashboard dynamic topic discovery

The topic bridge (`services/dashboard/backend/topics.py`) calls `node.get_topic_names_and_types()` every 5 s and dynamically subscribes to any new topic under `/perception/*` or `/fusion/*` whose type can be resolved via `rosidl_runtime_py.utilities.get_message()`. Topics whose type can't be imported (e.g. a future `atl4s_msgs/...` before the package is installed in the dashboard image) are added to `_discovered` anyway to avoid a hot-loop retry. Once you add a new perception service, rebuild the dashboard image to pick up its message package — the topic will appear automatically on the next 5 s tick.

## Service inventory

| # | Service | Status | Profile | Notes |
|---|---|---|---|---|
| 1 | `sitl` | running | sim | ArduCopter (`--model JSON`) + MAVProxy. `MAVPROXY_STREAMRATE` (default 10) controls `/mavros/*` rate. |
| 2 | `gazebo` | running | sim | Gazebo Harmonic 8.11 + `ardupilot_gazebo` plugin. Iris+gimbal in `iris_runway.sdf`. Headless EGL on the L4. SITL plugin on UDP 127.0.0.1:9002. |
| 3 | `gz-bridge` | running | sim | `ros_gz_bridge` mapping `/world/iris_runway/.../*` → `/camera/image`, `/camera/camera_info`, `/imu/gazebo`, `/clock`. One-way (GZ_TO_ROS). Add mappings in [services/gz-bridge/bridge.yaml](services/gz-bridge/bridge.yaml). |
| 4 | `mavros` | running | always | MAVLink ⇄ ROS 2 bridge via `apm.launch`. |
| 5 | `foxglove` | running | always | `foxglove_bridge 3.3.0` on TCP 8765. BE whitelist in `params.yaml`; `mavros_msgs` installed so Studio can call MAVROS services. Add the `-msgs` package of every new service that exposes services. |
| 6 | `commander` | running | always | Autonomy. Low-battery latch → `/mavros/set_mode RTL`. Threshold via `BATTERY_LOW_THRESHOLD`. |
| 7 | `healthcheck` | running | always | Topic-liveness monitor. Stdout summary + HTTP `/health` on 8088 + `/atl4s/health` (DiagnosticArray). |
| 8 | `rosbag-manager` | running | always | HTTP API for every bag-plane operation: record start/stop/status, watcher + GCS upload, GCS browser (list / upload / download / delete), and replay via `ros2 bag play`. Binds `127.0.0.1:8086` (loopback only). `FROM ros:humble`. Consumed by `dashboard`, `scripts/bag-record.sh`, and any future caller on the host. |
| 9 | `dashboard` | running | always | Single human-facing surface on TCP 8089 with HTTP Basic (`BAG_WEB_USER` / `BAG_WEB_PASS`). Streaming proxy to `rosbag-manager` under `/api/*`; `/ws/topics` + `/ws/camera` rclpy bridges in a daemon thread. Pages: Home, Live, Map (Leaflet), Bags (with metadata.yaml preview), Record, Replay, Pipelines (auto-discovers `/perception/*` and `/fusion/*`), Health. Foxglove deep link from Live + Replay. React + Vite + TS frontend; FastAPI + rclpy backend in one image. |
| 10 | `perception-detector` | planned | — | YOLO on `/camera/image`, L4 GPU. First use of `shared/atl4s_msgs/`. |
| 11 | `perception-segmenter` | planned | — | Segmentation. |
| 12 | `perception-fault` | planned | — | Fault / anomaly detection. |
| 13 | `perception-lidar` | planned | — | Point-cloud processing, once a lidar source exists (Gazebo gpu_lidar back-pressures the FDM loop — see Open items). |
| 14 | `fusion` | planned | — | Combines perception + pose into tracks / events. |
| 15 | `event-publisher` | planned | — | Application events → GCP Pub/Sub. |
| 16 | `ingestion` | planned | — | Zenoh bridge for ROS topics over WAN from the Orin (last). |

## Topic contracts

See [docs/ros-topics.md](docs/ros-topics.md). Stable namespaces:

- `/mavros/*` — managed by MAVROS.
- `/atl4s/*` — reserved for custom ATL4S outputs.
- `/perception/<modality>/<output>` — perception services.
- `/fusion/tracks`, `/atl4s/events` — fusion outputs.

## Open items

1. **More `commander` behaviors** — takeoff command, waypoint loop, geofence triggers, event publishing to `/atl4s/events`. Pure ROS 2 work, no new infrastructure.
2. **First perception service (`perception-detector`)** — stand up `shared/atl4s_msgs/` for Detection types, then `services/perception-detector` (CUDA base + YOLO on `/camera/image`). First use of the L4 GPU for inference.
3. **Drone integration (Orin Nano)** — Orin runs MAVProxy with `--out udp:<VM_external_IP>:14550`, open UDP 14550 in the firewall to the Orin's IP. Orin-side recording + upload calls `rosbag-manager`'s API to push real RealSense + lidar bags to GCS. Zenoh bridge for ROS topics over WAN comes at the end (`ingestion` service).
4. **B.3 — lidar in Gazebo (parked).** Attempted: gpu_lidar block in `services/gazebo/world/models/atl4s_lidar/` + composite `iris_with_lidar` model + `atl4s.sdf` world. Even at 90×4 rays @ 1 Hz the render back-pressures the JSON-FDM loop — SITL logs continuous `No JSON sensor message received, resending servos`. Retry path: lighter ray budget (e.g. 16×1), async sensor rendering, or skip Gazebo lidar entirely and validate `perception-lidar` against real Orin/RealSense data later. Files were rolled back; not in the repo today.
5. **Security tightening** — IAP-only SSH (`35.235.240.0/20`), Foxglove / web behind Tailscale, per-team IAM bindings. Defer until test phase is over.
6. **GCS bucket region** — bucket is us-east4 but VM is northamerica-northeast1; consider recreating co-located for production traffic.

## Commands reference

```bash
# Lifecycle
./scripts/dev-up.sh                       # SITL + downstream
./scripts/prod-up.sh                      # no SITL
./scripts/topic-check.sh                  # sanity check
docker compose --profile sim down         # stop everything

# Record + upload (via rosbag-manager API)
./scripts/bag-record.sh 30                # record 30s, wait for upload
./scripts/bag-list.sh                     # list bags in GCS
curl -fsS -X POST 127.0.0.1:8086/api/uploads/<bag-name>  # force-upload one bag (e.g. drop bags in by hand)

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
docker compose --profile sim down
docker rmi $(docker images atl4s/* -q)
docker compose --profile sim build --no-cache
./scripts/dev-up.sh

# VM cost control (~$17/day running, ~$0.07/day stopped)
gcloud compute instances stop  arachnid-atl4s-vm --zone=northamerica-northeast1-c
gcloud compute instances start arachnid-atl4s-vm --zone=northamerica-northeast1-c
```
