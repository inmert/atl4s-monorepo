# bag-record

Records selected ROS 2 topics to an mcap bag under `/data/bags/<name>/`.

## Configuration

| Env | Default | Description |
|---|---|---|
| `RECORD_TOPICS` | `/mavros/state /mavros/battery /mavros/global_position/global /mavros/imu/data /camera/image /camera/camera_info /imu/gazebo /clock` | Space-separated topic list passed to `ros2 bag record`. |
| `BAG_NAME` | `atl4s-<UTC timestamp>` | Bag directory name under `BAG_DIR`. |
| `BAG_DIR` | `/data/bags` | Where the bag is written (bind-mounted from `./data/bags` on the host). |

## Activation

Under the `record` profile so it does not run by default:

```bash
docker compose --profile sim --profile record up -d bag-record bag-uploader
```

The `bag-uploader` service watches the same directory and pushes completed bags to GCS automatically. See [scripts/bag-record.sh](../../scripts/bag-record.sh) for a wrapper that records for a fixed duration and stops cleanly.

## Stopping

`docker stop atl4s-bag-record`. SIGTERM reaches `ros2 bag record` (the entrypoint uses `exec`), which closes the bag cleanly. After ~15 s of stability, `bag-uploader` pushes it to GCS.

## QoS

`ros2 bag record` defaults its subscribers to Reliable, which silently misses every message from Best Effort publishers like `/mavros/*`. The entrypoint generates a per-topic Best Effort YAML at `/tmp/qos-overrides.yaml` and passes it via `--qos-profile-overrides-path`. Humble's parser accepts `topic: <dict>` and crashes on the more common `topic: [<dict>]` list form — the generated file uses the dict shape on purpose.
