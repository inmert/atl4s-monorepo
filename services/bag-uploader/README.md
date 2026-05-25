# bag-uploader

Watches `/data/bags` and pushes completed bag directories to `gs://${GCS_BUCKET}`. Idempotent across restarts via a `<bag>.uploaded` sentinel file written next to each uploaded bag.

A bag is considered "completed" once nothing inside it has been modified for `STABLE_SECONDS`. This avoids racing in-flight recordings.

## Configuration

| Env | Default | Description |
|---|---|---|
| `BAG_DIR` | `/data/bags` | Directory to watch (bind-mounted from `./data/bags`). |
| `GCS_BUCKET` | `atl4s-rosbags` | Target bucket. |
| `STABLE_SECONDS` | `15` | A bag is uploaded once nothing inside has changed for this long. |
| `POLL_SECONDS` | `10` | Watch loop interval. |

## Credentials

On the VM, the GCE metadata server provides credentials for the `atl4s-vm-sa` service account automatically — no key file required. On the Orin Nano (Phase 5), mount a service-account JSON and set `GOOGLE_APPLICATION_CREDENTIALS=/gcp-key.json`.

## Activation

Under the `record` profile, alongside `bag-record`:

```bash
docker compose --profile sim --profile record up -d bag-record bag-uploader
```

Standalone (e.g. to upload bags placed in `./data/bags/` by hand):

```bash
docker compose --profile record up -d bag-uploader
```
