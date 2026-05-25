# bag-web

Minimal FastAPI + HTML page for browsing, uploading, and deleting rosbags stored in `gs://${GCS_BUCKET}`.

A "bag" is one top-level prefix in the bucket (matches the layout `bag-uploader` produces from `ros2 bag record` output).

## Surfaces

- **HTML UI** — `http://<VM_external_IP>:${BAG_WEB_PORT}/` — table of bags, expandable file list, upload form, delete buttons.
- **JSON API** — same data, scriptable.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/bags` | List bags: `[{name, size_bytes, size_mib, files, updated}]` |
| `GET` | `/api/bags/{name}/files` | List files in a bag |
| `GET` | `/api/bags/{name}/files/{filename}` | Stream-download a file |
| `POST` | `/api/bags/{name}/upload` | Multipart upload; field name `files` (repeatable) |
| `DELETE` | `/api/bags/{name}` | Delete every blob under the prefix |
| `GET` | `/healthz` | Liveness (no GCS call) |

## Configuration

| Env | Default | Description |
|---|---|---|
| `GCS_BUCKET` | `atl4s-rosbags` | Target bucket. |
| `BAG_WEB_PORT` | `8089` | TCP port. Host networking. |

## Auth

None. Same exposure posture as the foxglove bridge — open on the host port. If you make the VM externally reachable on `:${BAG_WEB_PORT}`, anyone with the IP can delete bags. Put it behind Tailscale / IAP / a basic-auth proxy before exposing to the public internet.

## Examples

```bash
# List bags as JSON
curl -sS localhost:8089/api/bags | jq

# Upload a single mcap into a new prefix
curl -X POST -F "files=@my.mcap" localhost:8089/api/bags/my-test/upload

# Delete a bag (irreversible)
curl -X DELETE localhost:8089/api/bags/my-test
```

## Firewall

To reach this from your laptop, open TCP 8089 in the GCP firewall (`gcloud compute firewall-rules create allow-bag-web --action=allow --rules=tcp:8089 --source-ranges=<your IP>/32`). Don't open it to `0.0.0.0/0` while there's no auth.
