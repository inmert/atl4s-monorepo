# gazebo

Gazebo Harmonic running headless on the L4 GPU. Provides a 3D world and the [ArduPilot SITL plugin](https://github.com/ArduPilot/ardupilot_gazebo) — the bridge that lets an external ArduCopter binary fly inside the sim.

This is **B.1** of the perception roadmap. In **B.2** the `sitl` container will be rewired to connect to this Gazebo via the SITL plugin ports, and a `gz-bridge` container will republish Gazebo sensor topics into ROS 2.

## Configuration

| Env | Default | Description |
|---|---|---|
| `GZ_WORLD` | `iris_runway.sdf` | World file to load. Upstream worlds (`iris_runway.sdf`, `iris_maze.sdf`, …) ship in `/ardupilot_gazebo/worlds/`. Custom worlds in `/atl4s/worlds/` (currently `atl4s.sdf`). |

## Worlds

| World | Source | Notes |
|---|---|---|
| `iris_runway.sdf` | upstream | Bare iris on a runway. Used as the B.1 smoke world — proves the plugin loads. |
| `atl4s.sdf` | this repo (`world/atl4s.sdf`) | Iris in a small obstacle course (ground, two boxes, a wall). Will gain camera + lidar sensors in B.2. |

## GPU and rendering

The container requests one NVIDIA GPU via the Container Toolkit. Gazebo's sensor renderer uses Ogre2 with the EGL backend — no X display required. Verify GPU is wired through:

```bash
docker exec atl4s-gazebo nvidia-smi
```

## Inspecting from inside the container

```bash
docker exec atl4s-gazebo bash -c 'gz topic -l'           # all Gazebo topics
docker exec atl4s-gazebo bash -c 'gz model --list'       # spawned models
docker exec atl4s-gazebo bash -c 'gz sim -v'             # version
```

## Activation

Under the `sim` profile alongside `sitl`:

```bash
docker compose --profile sim up -d gazebo
```
