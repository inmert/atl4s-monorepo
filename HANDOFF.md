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
       └─ camera ──▶ gz-bridge ─▶ /camera/image, /camera/camera_info
                     (atl4s-gz-bridge)
```

- **Gazebo** runs `iris_runway.sdf` headless on the L4 GPU with the `ardupilot_gazebo` plugin loaded. Plugin listens on UDP 127.0.0.1:9002 for the JSON FDM stream.
- **SITL** runs `arducopter --model JSON --defaults copter.parm,gazebo-iris.parm`. Sensors (IMU, GPS, baro) come from Gazebo over JSON FDM. MAVLink still exposed on TCP 5760, fan-out to MAVROS unchanged via MAVProxy `--out udp:127.0.0.1:14550` (bidirectional).
- **gz-bridge** runs `ros_gz_bridge parameter_bridge` with a YAML config that renames the long Gazebo topic paths to short stable ROS 2 names. One-way (GZ_TO_ROS); MAVROS handles all commands into the vehicle.
- **MAVROS** binds UDP `0.0.0.0:14550`, uses `apm.launch` with a pruned plugin allowlist ([services/mavros/apm_pluginlists.yaml](services/mavros/apm_pluginlists.yaml)). ~18 plugins load (vs the upstream ~60), publishing ~50 topics under `/mavros/*` with **Best Effort** QoS — every plugin whose data a downstream service uses, plus setpoint/waypoint/geofence for upcoming commander work.
- All containers use `network_mode: host` so DDS discovery and same-host UDP work without per-service port maps.
- ROS topics over WAN (drone ↔ VM) will be bridged via Zenoh (`zenoh-bridge-ros2dds`) once Orin sensor topics are in scope.

### Key decisions

- **ArduPilot, not PX4.** SITL firmware matches the target drone.
- **MAVROS via `apm.launch`.** ArduPilot-specific entrypoint, not custom MAVLink parsing.
- **Docker Compose with profiles.** `--profile sim` enables SITL; production omits the profile.
- **Host networking everywhere.** No bridge networks, no per-container port maps.
- **Console runs on the host, not a container.** The operator dashboard (`console/`) is the `atl4s-console` systemd service on TCP 8089. It manages the stack (Docker socket, container lifecycle), so it must outlive `docker compose down` and not live inside what it controls. Runs as `arachnid` (in the `docker` group) against the local Docker socket; FastAPI in a venv, UI prebuilt to `console/ui/dist`. Replaced the old `services/dashboard` container (deleted).
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
├── console/                  Operator dashboard — runs on the HOST as the
│   │                         atl4s-console systemd service (TCP 8089), NOT a
│   │                         container. Replaced services/dashboard.
│   ├── api/                  FastAPI logic layer (auth, containers, deployments, pipelines, inspector + crackseg proxies)
│   ├── ui/                   React/Vite design layer (built to ui/dist)
│   ├── config/              deployments.yaml + pipelines.yaml registry + pipelines/{id}.yaml (RW; pipelines/ bind-mounted RO into perception-lidar + crackseg)
│   ├── deploy/ + scripts/    systemd unit template + setup/run/install scripts
│   └── requirements.txt
├── services/
│   ├── sitl/                 ArduPilot SITL + MAVProxy fan-out (sim profile)
│   ├── gazebo/               Gazebo Harmonic + ArduPilot SITL plugin (sim profile, headless GPU)
│   ├── gz-bridge/            Gazebo topics → ROS 2 names (sim profile)
│   ├── mavros/               MAVLink ⇄ ROS 2 bridge
│   ├── foxglove/             ROS 2 topics → WebSocket on TCP 8765
│   ├── commander/            Autonomy node: telemetry in, MAVROS commands out
│   ├── perception-lidar/     DBSCAN-based lidar detector — first user of `shared/atl4s_msgs/`
│   ├── rosbag-manager/       HTTP API for bag-plane ops: record / upload / GCS browser / replay (loopback 127.0.0.1:8086)
│   ├── inspector/            Backend engine for the console's 3D-model + rosbag viewer (loopback 127.0.0.1:8091)
│   └── crackseg/             Surface-defect inference (GPU) overlaid on the viewed model (loopback 127.0.0.1:8092)
├── shared/
│   ├── fastdds_profiles.xml  shared FastDDS XML (see gotchas)
│   └── atl4s_msgs/           ament_cmake message package (`LidarDetection`, `LidarDetectionArray` today). Built into the perception-lidar and foxglove images.
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
- MAVROS: bound on `0.0.0.0:14550`, link established. `/mavros/*` sensor topics at ~5 Hz (capped by ArduPilot below the requested 10). Plugin allowlist trims the loaded plugin count to ~18 (from upstream ~60); see [services/mavros/apm_pluginlists.yaml](services/mavros/apm_pluginlists.yaml) — add a name and rebuild to expose another plugin.
- gz-bridge: `/camera/image` (640×480 @ 5 Hz) and `/camera/camera_info` flowing as ROS 2 topics. `/imu/gazebo` and `/clock` were intentionally dropped — sim-only streams with no real-drone analog; production IMU is `/mavros/imu/data`.
- Foxglove: WebSocket on `0.0.0.0:8765`. BE whitelist covers `/mavros/.*`, `/uas1/.*` (raw MAVLink dropped silently without the last one), `/lidar/.*`, `/perception/.*`, `/fusion/.*`.
- Commander: low-battery → `set_mode RTL` verified end-to-end (forced via `BATTERY_LOW_THRESHOLD=1.0`).
- perception-lidar: subscribes to a configurable lidar input — `/lidar/points` (`sensor_msgs/PointCloud2` for 3D lidars, default) or `/lidar/scan` (`sensor_msgs/LaserScan` for 2D planar lidars) — selected via the `input_type` config field. Publishes `/perception/lidar/detections` (`atl4s_msgs/LidarDetectionArray`) for machine consumption and `/perception/lidar/markers` (`visualization_msgs/MarkerArray`) for Foxglove Studio's 3D panel (CUBE per detection, TEXT_VIEW_FACING label, DELETEALL prefix). Runtime config from `config/pipelines/perception-lidar.yaml`. DBSCAN + per-class shape priors (aircraft, tank); height is skipped from scoring when the input is 2D so the same priors work for both modalities. No live lidar source on the VM; verified end-to-end against `scripts/publish-fake-lidar.sh` (3D, ~5 Hz `PointCloud2`) and `scripts/publish-fake-scan.sh` (2D, ~5 Hz 720-ray `LaserScan`) — detections + markers stream at the input rate.
- rosbag-manager: HTTP API on `127.0.0.1:8086` for record / upload / GCS browser / replay. Smoke tested end-to-end via `./scripts/bag-record.sh` — record subprocess + watcher upload + GCS confirmed; replay downloads from GCS, plays, and cleans up `${REPLAY_DIR}`.
- console (operator dashboard, **runs on the host** as the `atl4s-console` systemd service on `:8089`): a fresh rebuild replacing the deleted `services/dashboard` container. Form login (signed httpOnly session cookie) reusing `BAG_WEB_USER` / `BAG_WEB_PASS`; typeui.sh "dashboard" design system (dark cloud-platform, light/dark toggle, IBM Plex Sans). Clean logic/design split — FastAPI `console/api/` is the only seam to the React `console/ui/`. Live pages: **Containers** (3-col cards; per-container detail drawer with live log stream + CPU/mem stats over WebSocket, start/stop/restart, log export, and **environment-variable view/edit** via container recreate), **Deployments** (CRUD registry of robots / vehicles / sensors — sim or real — with connection spec `protocol` + `host:port`; status derived from linked-container liveness; Gazebo Drone + Orin Drone seeded in `console/config/deployments.yaml`), **Inspector** (three.js FBX/GLB viewer with Blender-style middle-mouse controls + mesh/file metadata; rosbag browser — list / metadata / play-stop via the `inspector` backend; **Cracks** toggle overlays `crackseg` output on the model, captured on camera-settle), **Pipelines** (registry-driven cards — start/stop/restart any pipeline container via the Docker socket + a schema-generated config form persisted to `console/config/pipelines/{id}.yaml`; `crackseg` and `perception-lidar` declared). Placeholder pages: Dashboard, Rosbag Manager, Health, Settings — to be wired one at a time. Talks to Docker via the local socket as `arachnid` (no mounted socket). Setup: `console/scripts/setup.sh` then `install-service.sh`; logs via `journalctl -u atl4s-console -f`.
- inspector (loopback `127.0.0.1:8091`): backend engine for the console's viewer (no UI of its own — the console proxies it under `/api/inspector/*`). Stores + serves uploaded 3D models (`/data/models`); rosbag list / metadata / play-stop delegate to `rosbag-manager`. `FROM python:3.11-slim` (no ROS). The console serves the three.js viewer.
- crackseg (loopback `127.0.0.1:8092`, L4 GPU): surface-defect inference whose RGBA mask the inspector overlays on the model in view. Two interchangeable methods (`method` config): `color` (CIELAB local colour-discrepancy, no weights — flags marks that differ in colour) and `unet` (swappable UNet / TorchScript / state_dict from a mounted weights dir). CUDA torch base. Started/stopped/configured from the Pipelines page.

Verify:

```bash
# MAVROS link
docker exec atl4s-mavros bash -c \
  "source /opt/ros/humble/setup.bash && \
   ros2 topic echo /mavros/state --qos-reliability best_effort --once"

# Console service (host)
systemctl is-active atl4s-console            # -> active
curl -sS localhost:8089/healthz | jq         # -> {"status":"ok"}

# Console login (form auth → session cookie) + containers via the host socket
curl -sS -c /tmp/cj -X POST localhost:8089/api/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${BAG_WEB_USER}\",\"password\":\"${BAG_WEB_PASS}\"}"
curl -sS -b /tmp/cj localhost:8089/api/containers | jq '.containers | length'
```

Browser: `https://studio.foxglove.dev/` → Open connection → Foxglove WebSocket → `ws://<VM_external_IP>:8765`. Console at `http://<VM_external_IP>:8089/`.

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

1. **BE publisher + Reliable sub → no data.** Fix via the `best_effort_qos_topic_whitelist` regex list in [services/foxglove/params.yaml](services/foxglove/params.yaml). Current entries: `/mavros/.*`, `/uas1/.*`, `/lidar/.*`, `/perception/.*`, `/fusion/.*`. Add new BE namespaces here when you create services.
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

### `/uas1/*` topics are mavros internal plumbing

The `/uas1/mavlink_source` (~138 Hz, FCU → us) and `/uas1/mavlink_sink` (~12 Hz, us → FCU) topics are mavros's internal IPC, not user-facing. mavros runs as two cooperating processes: `mavros_router` owns the UDP socket and republishes raw MAVLink frames on `/uas1/mavlink_source`; `mavros_node` consumes them, parses MAVLink into the typed `/mavros/*` topics, and publishes commands on `/uas1/mavlink_sink` that `mavros_router` ferries back to the FCU. The only subscriber to either topic is mavros itself.

Implications: (1) they cannot be removed — disabling them breaks mavros end-to-end. (2) they explain why `/uas1/.*` is on the foxglove BE whitelist (without it, raw MAVLink panels in Studio show empty under default Reliable). (3) adding a second MAVLink endpoint (e.g. the Orin Nano on a separate UDP channel) would create `/uas2/*` for that endpoint; routing the Orin through the same MAVProxy fan-out into UDP 14550 keeps everything on `/uas1/*` instead.

### `/mavros/param/get` looks like a service but has no server

`ros2 service list -t` reports `/mavros/param/get [mavros_msgs/srv/ParamGet]` and `ros2 service type` resolves it cleanly — but `ros2 service call /mavros/param/get …` hangs at `waiting for service to become available...` and then exits with a noisy `failed to check service availability: rcl node's context is invalid` message. The error line is a CLI teardown artifact, not the real failure; the underlying call is `wait_for_service` correctly returning `False`.

Cause: `mavros_msgs/srv/ParamGet` is a **mavros 1.x legacy service**. mavros 2.x replaced it with the standard `rcl_interfaces` parameter API (`/mavros/param/get_parameters`, `/mavros/param/set_parameters`, …), so no node hosts the legacy service anymore. The reason it still shows in the graph is that **`foxglove_bridge` registers a service _client_ for it** (`ros2 node info /foxglove_bridge | grep param/get` confirms). ROS 2's service introspection happily lists a service the moment any participant — client or server — advertises the name, which makes a phantom service indistinguishable from a real one at first glance.

How to tell client-only from server-backed: `ros2 service find <type>` returns names known to the graph; **`ros2 node info <node>`** is the only canonical way to see which side (Server vs Client) each node owns. To call the parameter API on mavros, use `/mavros/param/get_parameters` (and call `/mavros/param/pull` first to populate the FCU cache).

### `ArduPilot controller has reset` warning

Steady ~0.6/min in `atl4s-gazebo` logs (`[Wrn] [ArduPilotPlugin.cc:1599]`). This is the `ardupilot_gazebo` plugin re-syncing with the SITL JSON-FDM channel after the occasional UDP packet drops between containers — `network_mode: host` shares the namespace but Linux still drops sub-microsecond bursts under load. Harmless at this rate (the plugin re-converges within one tick). Investigate only if the rate climbs above ~10/min or telemetry actually glitches.

### `ros2 bag record` QoS override YAML

`ros2 bag record` defaults its subscribers to Reliable. To capture `/mavros/*` (Best Effort) you must pass `--qos-profile-overrides-path` with per-topic profiles. The YAML shape Humble's parser accepts is `topic: <dict>`, **not** `topic: [<dict>]` — the more common list form crashes with `'list' object has no attribute 'items'`. `rosbag-manager` (`app/record.py`) generates the correct shape per recording from the request's `topics` list.

### Compose volume merge

Same trap as the env merge above: a service-level `volumes:` list silently replaces `x-common.volumes`. Any service that adds its own volume mounts must re-declare the FastDDS profile mount or lose it. `rosbag-manager` and `perception-lidar` both do this with a one-line comment at the call site.

### Shared message packages → repo-root build context

Two services (`foxglove`, `perception-lidar`) use `shared/atl4s_msgs/` and therefore declare `build.context: .` + `build.dockerfile: services/<svc>/Dockerfile` in compose, rather than the standard `context: ./services/<svc>`. Their Dockerfiles `COPY shared/atl4s_msgs /workspace/src/atl4s_msgs` and `colcon build --packages-select atl4s_msgs --merge-install`; the entrypoint sources `/workspace/install/setup.bash` on top of `/opt/ros/humble/setup.bash`.

Any future service that publishes or subscribes to an `atl4s_msgs/*` type follows the same pattern. Without it the type won't deserialize and the topic appears blank in Foxglove.

A repo-root `.dockerignore` keeps the context=. builds from shipping the whole repo (data/, .git, node_modules, **/dist) to the Docker daemon every build.

> The three gotchas below describe the **retired `services/dashboard` container** (deleted; replaced by the host `console`). The console has no ROS bridge yet, but these still apply verbatim when it adds live telemetry — keep them.

### ROS `float` NaN/Inf → invalid JSON over the WebSocket

ROS messages routinely carry `NaN` in optional fields the source can't measure — ArduPilot reports `sensor_msgs/BatteryState.charge`, `.capacity`, and `.design_capacity` as NaN every frame, and many other sensor types do the same. Python's default `json.dumps` emits these as the literal token `NaN` (and `Infinity`/`-Infinity`), which is not valid JSON per RFC 8259. The browser's `JSON.parse` throws on the whole frame, every consumer of that topic sees no data, and any stat tile / panel that reads those values shows `"—"` because the topic entry never appears in the React state map.

The dashboard sanitizes in `services/dashboard/backend/topics.py:_sanitize_for_json` — walks the OrderedDict that `message_to_ordereddict` returns and replaces NaN/Inf floats with `None`. The frontend's `value != null ? value : '—'` check then correctly falls through to the placeholder for that one field while keeping the rest of the message visible. Any new path that ships a ROS message to a JSON consumer (custom widgets, future `/api/*` returning live telemetry) needs the same sanitize.

### ROS `byte` field → 1-char string in JSON

`rosidl_runtime_py.message_to_ordereddict()` represents ROS `byte` fields as 1-character `str`, not `int`. `diagnostic_msgs/DiagnosticStatus.level` is the obvious one (`b'\x00'` becomes `"\u0000"` in the JSON the dashboard ships to the browser). The dashboard frontend coerces via `String.charCodeAt(0)` in `pages/Health.tsx` and `App.tsx`. Other byte fields to watch for if they ever surface: `sensor_msgs/BatteryState.power_supply_status`, `sensor_msgs/Imu` orientation_covariance (no, that's float).

### Console auth across WebSocket upgrades

The console uses a **signed httpOnly session cookie** (not HTTP Basic) — `console/api/auth.py`. The cookie is set by `POST /api/auth/login` and rides along on same-origin requests, including the `/ws/containers/*` upgrade, so `auth.check_websocket()` validates it from `ws.cookies`. Because it's set after login, open the SPA and sign in before any direct `/ws/*` test from a browser; for curl, capture the cookie jar from the login call and pass it on the WS request.

### Loopback backends behind the console proxy

`inspector` (`:8091`), `crackseg` (`:8092`) and `rosbag-manager` (`:8086`) bind **loopback only** and are never exposed to browsers. The console (a host process, so it reaches `127.0.0.1`) proxies them under `/api/inspector/*`, `/api/crackseg/*`, `/api/pipelines` — same-origin and gated by the session cookie, with `httpx` streaming uploads/downloads. So: the only browser-facing port is the console's 8089; new such services follow the same pattern (loopback container + a console proxy module + a UI page). The console serves the heavy UI (e.g. the three.js viewer); the backend stays a thin engine, GPU-ready (crackseg reserves the L4 like `gazebo`).

## Service inventory

| # | Service | Status | Profile | Notes |
|---|---|---|---|---|
| 1 | `sitl` | running | sim | ArduCopter (`--model JSON`) + MAVProxy. `MAVPROXY_STREAMRATE` (default 10) controls `/mavros/*` rate. |
| 2 | `gazebo` | running | sim | Gazebo Harmonic 8.11 + `ardupilot_gazebo` plugin. Iris+gimbal in `iris_runway.sdf`. Headless EGL on the L4. SITL plugin on UDP 127.0.0.1:9002. |
| 3 | `gz-bridge` | running | sim | `ros_gz_bridge` mapping `/world/iris_runway/.../*` → `/camera/image`, `/camera/camera_info`. One-way (GZ_TO_ROS). Sim-only `/imu/gazebo` and `/clock` deliberately not bridged (no real-drone analog). Add mappings in [services/gz-bridge/bridge.yaml](services/gz-bridge/bridge.yaml). |
| 4 | `mavros` | running | always | MAVLink ⇄ ROS 2 bridge via `apm.launch`. Plugin allowlist in [services/mavros/apm_pluginlists.yaml](services/mavros/apm_pluginlists.yaml) — 18 plugins load (vs upstream ~60), ~50 `/mavros/*` topics on the bus. |
| 5 | `foxglove` | running | always | `foxglove_bridge 3.3.0` on TCP 8765. BE whitelist in `params.yaml`; `mavros_msgs` installed so Studio can call MAVROS services. Add the `-msgs` package of every new service that exposes services. |
| 6 | `commander` | running | always | Autonomy. Low-battery latch → `/mavros/set_mode RTL`. Threshold via `BATTERY_LOW_THRESHOLD`. |
| 7 | `rosbag-manager` | running | always | HTTP API for every bag-plane operation: record start/stop/status, watcher + GCS upload, GCS browser (list / upload / download / delete), and replay via `ros2 bag play`. Binds `127.0.0.1:8086` (loopback only). `FROM ros:humble`. Consumed by the console, `scripts/bag-record.sh`, and any future caller on the host. |
| — | `console` | running | host service | **Not a container.** Operator dashboard on the host as the `atl4s-console` systemd service (TCP 8089). FastAPI (`console/api`) + React (`console/ui`). Form login (session cookie) reusing `BAG_WEB_USER`/`BAG_WEB_PASS`. Live: **Containers** (logs/stats streams, start·stop·restart, log export, env edit) and **Deployments** (robot/sensor registry). See [console/README.md](console/README.md). |
| 8 | `perception-lidar` | running (no input yet) | always | First perception service + first user of `shared/atl4s_msgs/`. Subscribes to the configured lidar input — `/lidar/points` (`sensor_msgs/PointCloud2`) or `/lidar/scan` (`sensor_msgs/LaserScan`) per `input_type`. Publishes `/perception/lidar/detections` (`atl4s_msgs/LidarDetectionArray`) + `/perception/lidar/markers` (`visualization_msgs/MarkerArray`, rendered by Foxglove Studio's 3D panel). Classical scaffold today: DBSCAN cluster → AABB → per-class shape priors (aircraft = elongated + flat, tank = compact + cubic); height is skipped from scoring for 2D inputs. Runtime config read from `console/config/pipelines/perception-lidar.yaml` (bind-mounted RO). `_classify` / `_score` in `lidar_detector.py` are the swap-in points for a learned model later. No live lidar source on the VM today; use `scripts/publish-fake-lidar.sh` (3D PointCloud2) or `scripts/publish-fake-scan.sh` (2D LaserScan) to drive synthetic frames. |
| 9 | `inspector` | running | always | Backend engine for the console's 3D-model + rosbag viewer. Loopback `127.0.0.1:8091`; the console proxies `/api/inspector/*` and serves the three.js UI. Stores uploaded models in `/data/models`; rosbag list/metadata/play delegate to `rosbag-manager`. `FROM python:3.11-slim` (no ROS). |
| 10 | `crackseg` | running | always | Surface-defect inference (L4 GPU) overlaid on the inspector model. Loopback `127.0.0.1:8092`. `method: color` (CIELAB colour-discrepancy, no weights) or `unet` (swappable UNet / TorchScript / state_dict via `./data/crackseg/weights`). Start/stop/configure from the Pipelines page. |
| 11 | `perception-detector` | planned | — | YOLO on `/camera/image`, L4 GPU. |
| 12 | `perception-segmenter` | planned | — | Segmentation. |
| 13 | `perception-fault` | planned | — | Fault / anomaly detection. |
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

1. **Console (operator dashboard) — in progress.** Host `atl4s-console` systemd service (TCP 8089; FastAPI + React, form-login session auth). Done: login, **Containers**, **Deployments**, **Inspector** (3D-model + rosbag viewer with the `crackseg` defect overlay), **Pipelines** (start/stop/restart + schema config form over the Docker socket). Remaining pages to wire one at a time: **Dashboard** (fleet overview), **Rosbag Manager** (the Inspector already browses/plays bags; this page would add record/upload), **Health** (containers + topic liveness), **Settings**. Telemetry/ROS (live topics, camera, map) will reuse the host's `rclpy` — see the NaN/byte gotchas above.
   - **crackseg defect model.** Committed today is `method: color` (CIELAB colour-discrepancy) + a swappable `unet`. The colour method over-fires on textured/multi-colour assets; a CarDD YOLOv11 vehicle-damage model (Ultralytics) was prototyped as a better fit and can be re-added as a `yolo` method. The cleanest path for a specific asset is a model trained for it, dropped into `./data/crackseg/weights` (TorchScript / state_dict) — no rebuild.
2. **Real lidar input + learned detector for `perception-lidar`.** The service is wired and running today (`4d1408a`) with a DBSCAN + geometric-prior scaffold. Two follow-ups when the data arrives:
    - **Input source.** No live lidar publishes `/lidar/points` on the VM yet. Synthetic frames via `scripts/publish-fake-lidar.sh` validate the wiring. Real options: (a) Orin's lidar via the future `ingestion` service (Zenoh), (b) revisit the parked Gazebo gpu_lidar attempt with a lighter ray budget, (c) replay a real lidar bag in.
    - **Learned model.** Replace `_classify` / `_score` in `services/perception-lidar/lidar_detector.py` with a CUDA-backed PointPillars / CenterPoint / VoxelNet inference path (the config `model_variant` already selects between them; today it logs a warning that the value is a no-op). First use of the L4 GPU for inference. Needs aircraft/tank training data, since public KITTI/nuScenes checkpoints target car/pedestrian/cyclist instead.
3. **More `commander` behaviors** — takeoff command, waypoint loop, geofence triggers, event publishing to `/atl4s/events`. Pure ROS 2 work, no new infrastructure.
4. **Drone integration (Orin Nano)** — Orin runs MAVProxy with `--out udp:<VM_external_IP>:14550`, open UDP 14550 in the firewall to the Orin's IP. Orin-side recording + upload calls `rosbag-manager`'s API to push real RealSense + lidar bags to GCS. Zenoh bridge for ROS topics over WAN comes at the end (`ingestion` service). The Orin Drone is already a first-class entry in the console's deployment registry (`console/config/deployments.yaml`, offline until integration).
5. **Lidar in Gazebo (parked).** Attempted: gpu_lidar block in `services/gazebo/world/models/atl4s_lidar/` + composite `iris_with_lidar` model + `atl4s.sdf` world. Even at 90×4 rays @ 1 Hz the render back-pressures the JSON-FDM loop — SITL logs continuous `No JSON sensor message received, resending servos`. Retry path: lighter ray budget (e.g. 16×1), async sensor rendering, or skip Gazebo lidar entirely and validate `perception-lidar` against real Orin/RealSense data later. Files were rolled back; not in the repo today.
6. **Security tightening** — IAP-only SSH (`35.235.240.0/20`), Foxglove / web behind Tailscale, per-team IAM bindings. Defer until test phase is over.
7. **GCS bucket region** — bucket is us-east4 but VM is northamerica-northeast1; consider recreating co-located for production traffic.

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

# Perception-lidar without a real lidar source
./scripts/publish-fake-lidar.sh           # ~5 Hz synthetic /lidar/points (Ctrl-C to stop)

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
