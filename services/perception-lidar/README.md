# perception-lidar

First user of `shared/atl4s_msgs/`. Subscribes to a lidar input topic — `sensor_msgs/PointCloud2` for 3D lidars or `sensor_msgs/LaserScan` for planar 2D lidars — clusters the (above-ground, within-range) points with DBSCAN, classifies each cluster against per-class shape priors, and publishes both `atl4s_msgs/LidarDetectionArray` (machine-readable) and `visualization_msgs/MarkerArray` (Foxglove Studio 3D panel renders this natively as labelled boxes).

## Pipeline shape

```
sensor_msgs/PointCloud2  ─┐
sensor_msgs/LaserScan    ─┤  (either; selected via input_type)
                          ▼
                   [ Nx3 xyz array ]
                          ▼
            [ ground + range filter ]
                          ▼
                  [ DBSCAN cluster ]
                          ▼
       [ AABB → score against PROTOTYPES ]
                          ▼
       [ filter by target_classes + confidence_threshold ]
                          ▼
            ┌─────────────┴─────────────┐
            ▼                           ▼
 atl4s_msgs/LidarDetectionArray   visualization_msgs/MarkerArray
   (machine-readable output)       (CUBE + TEXT per detection;
                                     Foxglove 3D panel renders directly)
```

For LaserScan inputs the projection maps each ray to `(r·cos θ, r·sin θ, 0)`; the ground filter (z > −1.0 m) is a no-op for 2D and the range filter still rejects far returns. Bounding-box height is 0 for every 2D detection, so the scoring step skips the height-axis fit and discriminates on length + width + aspect ratio alone (`_score` in [lidar_detector.py](lidar_detector.py)).

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
| `input_type` | `pointcloud2` | `pointcloud2` for 3D lidars (`sensor_msgs/PointCloud2`) or `laserscan` for 2D planar lidars (`sensor_msgs/LaserScan`). |
| `input_topic` | `/lidar/points` | Topic to subscribe to (type is selected by `input_type`). |
| `output_topic` | `/perception/lidar/detections` | LidarDetectionArray topic to publish on. |
| `marker_topic` | `/perception/lidar/markers` | MarkerArray output for Foxglove Studio's 3D panel — one CUBE + TEXT marker per detection, with a DELETEALL prefix so old markers don't linger. |
| `enable_tracking` | `false` | Logged; tracking not implemented yet (track_id is always 0). |

## Viewing live output in Foxglove Studio

Add a 3D panel to your layout and subscribe it to `marker_topic` (default `/perception/lidar/markers`). Each detection renders as a coloured cube — orange for `aircraft`, red for `tank`, grey for any other label — with the class id and score floating above it as text. The frame is whatever frame_id the input message carries (`lidar` for both synthetic publishers). Foxglove will treat that as a root frame unless you publish a TF.

The dashboard's Pipelines page also discovers and shows the marker topic in the "live output rates" section of the perception-lidar drawer; the `/ws/ros/sample/{topic}` inspector can dump raw frames.

## Testing without real lidar

The L4 VM has no lidar source yet (the Gazebo gpu_lidar attempt is parked — see HANDOFF.md "Open items"). Use the synthetic publishers to drive frames.

3D path (set `input_type: pointcloud2` and `input_topic: /lidar/points`):

```bash
./scripts/publish-fake-lidar.sh
```

Publishes ~5 Hz `PointCloud2` frames containing a tank-shaped point blob, an aircraft-shaped point blob, and some random noise. Expect two `tank` detections per frame (score ~0.5–0.8); the aircraft cluster usually splits under the current DBSCAN epsilon and is filtered as `other` — increase `DBSCAN_EPS` in the source if you want aircraft detections on synthetic data.

2D path (set `input_type: laserscan` and `input_topic: /lidar/scan`, then restart the container):

```bash
./scripts/publish-fake-scan.sh
```

Publishes ~5 Hz 720-ray `LaserScan` frames (360° coverage) with the same tank + aircraft footprints rendered as solid AABB returns. Detections have `size.z = 0`; the marker bridge clamps cube height to 5 cm so they still render as thin slabs in Foxglove.

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
- publish `/perception/lidar/detections` and `/perception/lidar/markers` (both auto-discovered by the dashboard's topic bridge under `/perception/*`).

When the container is up and running, the dashboard's Pipelines card flips from "Not deployed" to "Running" and Start/Stop/Restart all work via the docker socket.
