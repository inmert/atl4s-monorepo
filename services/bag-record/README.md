# bag-record

Records selected ROS 2 topics to an mcap bag under `/data/bags/<name>/`.

## Configuration

| Env | Default | Description |
|---|---|---|
| `RECORD_TOPICS` | `/mavros/state /mavros/battery /mavros/global_position/global /mavros/imu/data` | Space-separated topic list passed to `ros2 bag record`. |
| `BAG_NAME` | `atl4s-<UTC timestamp>` | Bag directory name under `BAG_DIR`. |
| `BAG_DIR` | `/data/bags` | Where the bag is written (bind-mounted from `./data/bags` on the host). |

## Activation

Under the `record` profile so it does not run by default:

```bash
docker compose --profile sim --profile record up -d bag-record uploader
```

The `uploader` service watches the same directory and pushes completed bags to GCS automatically. See [scripts/bag-record.sh](../../scripts/bag-record.sh) for a wrapper that records for a fixed duration and stops cleanly.

## Stopping

`docker stop atl4s-bag-record`. SIGTERM reaches `ros2 bag record` (the entrypoint uses `exec`), which closes the bag cleanly. After ~15 s of stability, `uploader` pushes it to GCS.

## QoS

`/mavros/*` topics are Best Effort. `ros2 bag record` defaults to Reliable, which would silently miss messages. `--qos-profile-overrides-path /dev/null` falls back to matching the publisher's offered QoS — this matters and should not be removed.
