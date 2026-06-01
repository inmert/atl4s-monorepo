# mesh-worker

Cloud Run service that builds Poisson meshes from ARACHNID scan bags.

## Architecture

```
iPad/Vercel POST /api/aws/bag/mesh-build
  ├─ S3:     PUT sites/{site}/scans/{scan}/mesh-request.json   (sentinel)
  └─ PubSub: publish { site_id, scan_id } to mesh-build-requests
        └─ push subscription → POST https://<cloud-run-url>/
              ├─ idempotency check: skip if gs://.../mesh.ply already exists
              ├─ Vercel /api/aws/bag/get-url → download scan.bag
              ├─ mirror scan.bag → gs://arachnid-rosbag-bucket/{site}/{scan}/scan.bag
              ├─ pyrealsense2 playback → Open3D Poisson mesh
              ├─ upload mesh.ply → GCS
              └─ Vercel /api/aws/bag/upload-url → PUT mesh.ply to S3
```

The worker reaches S3 only via the existing Vercel presigned-URL
endpoints, so no AWS credentials live on Cloud Run.

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | python:3.11-slim + libgl1/libusb runtime |
| `requirements.txt` | flask, gunicorn, google-cloud-storage, open3d, pyrealsense2 |
| `main.py` | Flask app; one POST `/` endpoint that decodes a Pub/Sub push envelope |
| `build_mesh.py` | The mesh pipeline itself (fetch → mirror → mesh → upload) |
| `.dockerignore` | keeps __pycache__ out of the build context |

## Deploy

From the repo root:

```bash
./scripts/gcp-deploy-mesh-worker.sh
```

This script enables the required APIs, creates an Artifact Registry
repo, two service accounts (worker + Vercel publisher), the Pub/Sub
topic, builds the image with Cloud Build, deploys Cloud Run, and
creates the push subscription pointing at the new service URL.

After it finishes, it prints next-step instructions for exporting a
service-account key and adding three env vars to Vercel:

- `GCP_SA_KEY_B64` — base64-encoded JSON key for `vercel-publisher-sa`
- `GCP_PROJECT_ID` — `arachnid-atlas`
- `GCP_PUBSUB_TOPIC` — `mesh-build-requests`

## Local dev

```bash
cd mesh-worker
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Auth as yourself so storage.Client() can hit GCS:
gcloud auth application-default login
GCS_BUCKET=arachnid-rosbag-bucket python main.py
# In another shell, simulate a Pub/Sub push:
curl -X POST http://localhost:8080/ -H 'Content-Type: application/json' \
  -d "$(python3 -c '
import base64, json
data = base64.b64encode(json.dumps({
    "site_id": "ipad-pro-m4",
    "scan_id": "arachnid-2026-05-13T23-40-30Z"
}).encode()).decode()
print(json.dumps({"message": {"data": data, "messageId": "local-1"}}))')"
```

Note: pyrealsense2 has no macOS arm64 wheel, so local dev needs a
Linux x86_64 host (or `docker run`).

## Tunable env vars

| Var | Default | Notes |
|---|---|---|
| `VERCEL_API` | `https://arachnid-flight.vercel.app` | Source of presigned URLs |
| `GCS_BUCKET` | `arachnid-rosbag-bucket` | Where bags + meshes mirror to |
| `MESH_VOXEL` | `0.02` | Per-frame downsample (m) |
| `MESH_DEPTH_TRUNC` | `5.0` | Max depth (m); drops sentinel 0xFFFF |
| `MESH_POISSON_DEPTH` | `9` | Higher = finer mesh, more memory |
| `MESH_FRAME_STRIDE` | `4` | Use every Nth frame |
| `MESH_MIN_POINTS` | `1000` | Bail if accumulation produces fewer points |

## Idempotency

Pub/Sub may redeliver a message if the worker doesn't ack within the
subscription's `ack_deadline` (we set 600 s). The worker checks for
`gs://{GCS_BUCKET}/{site}/{scan}/mesh.ply` at the start of each
request and returns `{ skipped: true }` if it exists. Force a rebuild
by deleting that object first.

## Known limitations

- **Synthetic bags fail to open.** Bags written by
  `scripts/build-scan-from-coords.py` (the demo/synth path) are
  missing the `/file_version` librealsense magic-marker topic.
  pyrealsense2 refuses them with `Invalid file format`. iPad-recorded
  bags work because RSBagUploader writes the topic. Either fix the
  synth writer, or switch this worker to use `rosbags` for reading.
- **Pose stream is dropped.** Pyrealsense2's `pose_frame` only
  surfaces on T265 devices; for iPad bags the SDK silently ignores
  the software-emitted pose topic, so accumulation is in
  camera-frame coords (not world-frame). Mesh isn't anchored — same
  caveat as `scripts/build-scan-mesh.py`.
