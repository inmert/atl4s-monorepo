# gazebo

Gazebo Harmonic running headless on the L4 GPU. Provides a 3D world and the [ArduPilot SITL plugin](https://github.com/ArduPilot/ardupilot_gazebo) — the bridge that lets the external ArduCopter binary in `services/sitl` fly inside the sim. Sensor topics emitted here are renamed by `services/gz-bridge` for downstream consumers.

## Configuration

| Env | Default | Description |
|---|---|---|
| `GZ_WORLD` | `iris_runway.sdf` | World file to load. Upstream worlds (`iris_runway.sdf`, `iris_maze.sdf`, …) ship in `/ardupilot_gazebo/worlds/`. |

## Worlds

| World | Source | Notes |
|---|---|---|
| `iris_runway.sdf` | upstream | Bare iris on a runway. Current default; what the pipeline is verified against. |

## GPU and rendering

The container requests one NVIDIA GPU via the Container Toolkit. Gazebo's sensor renderer uses Ogre2 with the EGL backend — no X display required. Verify GPU is wired through:

```bash
docker exec atl4s-gazebo nvidia-smi
```

## Inspecting from inside the container

```bash
docker exec atl4s-gazebo bash -c 'gz topic -l'        # all Gazebo topics
docker exec atl4s-gazebo bash -c 'gz model --list'    # spawned models
docker exec atl4s-gazebo bash -c 'gz sim -v'          # version
```

## Activation

Under the `sim` profile alongside `sitl` and `gz-bridge`:

```bash
docker compose --profile sim up -d gazebo
```
