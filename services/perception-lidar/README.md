# perception-lidar

First user of `shared/atl4s_msgs/`. Subscribes to a PointCloud2 input topic, clusters the (above-ground, within-range) points with DBSCAN, classifies each cluster against per-class shape priors, and publishes the surviving detections as `atl4s_msgs/LidarDetectionArray`.

## Pipeline shape

```
sensor_msgs/PointCloud2  ─┐
                          ▼
            [ ground + range filter ]
                          ▼
                  [ DBSCAN cluster ]
                          ▼
       [ AABB → score against PROTOTYPES ]
                          ▼
       [ filter by target_classes + confidence_threshold ]
                          ▼
         atl4s_msgs/LidarDetectionArray
```

## Detector

Classical scaffold today: DBSCAN + per-class geometric scoring. Honest about it:

- Loads `model_variant` from config and logs a warning that pointpillars / centerpoint / voxelnet are no-ops until a learned model is wired.
- Shape priors live in `PROTOTYPES` at the top of [lidar_detector.py](lidar_detector.py). Adding a class is one entry there.
- Score is the geometric mean of per-axis fit (length / width / height / length-over-width) against the prior — one bad axis dominates.
- To swap in a real model, replace `_classify` / `_score` (and add a model loader); the rest of the node stays.

## Configuration

Read once at startup from `${LIDAR_CONFIG}` (default `/app/config/pipelines/perception-lidar.yaml`). The dashboard's Pipelines page writes that file; **click Restart in the dashboard for changes to apply** (the file is not hot-reloaded).

| Field | Default | What it does |
|---|---|---|
| `model_variant` | `pointpillars` | Logged; otherwise a no-op until a learned model is wired. |
| `confidence_threshold` | `0.5` | Drop detections whose geometric-fit score is below this. |
| `target_classes` | `[aircraft, tank]` | Only publish detections whose label is in this list. |
| `input_topic` | `/lidar/points` | PointCloud2 topic to subscribe to. |
| `output_topic` | `/perception/lidar/detections` | LidarDetectionArray topic to publish on. |
| `enable_tracking` | `false` | Logged; tracking not implemented yet (track_id is always 0). |

## Testing without real lidar

The L4 VM has no lidar source yet (the Gazebo gpu_lidar attempt is parked — see HANDOFF.md "Open items"). Use the synthetic publisher to drive frames:

```bash
./scripts/publish-fake-lidar.sh
```

Runs a one-off container that publishes ~5 Hz `PointCloud2` frames on `/lidar/points`, each containing a tank-shaped point blob and an aircraft-shaped point blob (with some random noise points). `perception-lidar` should pick them up and publish two detections per frame; verify via Foxglove or the dashboard's ROS page inspecting `/perception/lidar/detections`.

## Image internals

`Dockerfile` is built from the repo root so it can pick up `shared/atl4s_msgs/`:

```yaml
build:
  context: .
  dockerfile: services/perception-lidar/Dockerfile
```

The image colcon-builds `atl4s_msgs` into `/workspace/install/`; the entrypoint sources that overlay on top of `/opt/ros/humble/setup.bash` before running the node.

Python deps (CPU only today): numpy, scikit-learn (DBSCAN), pyyaml. ~700 MB image.

## Container ↔ dashboard contract

The dashboard's Pipelines page expects this service to:
- be named `atl4s-perception-lidar`,
- bind-mount `services/dashboard/config/pipelines/` so it reads the same `perception-lidar.yaml` the dashboard writes,
- publish `/perception/lidar/detections` (auto-discovered by the dashboard's topic bridge under `/perception/*`).

When the container is up and running, the dashboard's Pipelines card flips from "Not deployed" to "Running" and Start/Stop/Restart all work via the docker socket.
