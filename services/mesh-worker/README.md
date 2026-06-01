# mesh-worker

VM-resident Pub/Sub pull subscriber that processes iPad scan bags into
mesh + defect artifacts, alongside crackseg.

## Pipeline

  scan.bag in S3 (Vercel publishes to Pub/Sub topic inspection-requests)
      |
      v
  vm_worker.py pulls the message
      |
      v
  build_mesh.py runs ONE bag-playback loop with three FrameSinks:
      MeshAccumulator    -> mesh.ply + mesh.glb
      PoseAccumulator    -> walked-path translations
      DefectTracker      -> voxel-hash dedup (defects.json v3)
      |
      v
  renders.py (Open3D OffscreenRenderer + GPU)
      -> splat.png, path.png
      |
      v
  All artifacts mirrored to GCS, pushed to S3 via Vercel presigned URLs.

The PDF report builder (in flight-ui-static/scripts/build-scan-report.mjs)
consumes defects.json + splat.png + path.png to assemble the operator
deliverable.

## Files

| File | Purpose |
| --- | --- |
| Dockerfile             | image used by the running atl4s-mesh-worker container |
| Dockerfile.cloudrun.legacy | superseded Flask + gunicorn entrypoint for Cloud Run |
| vm_worker.py           | Pub/Sub pull subscriber + healthz server |
| build_mesh.py          | bag-playback loop, sinks, variant generation |
| defects/grid.py        | Voxel + project_to_world + build_T_cw |
| defects/state.py       | DefectTracker (candidate/confirmed state machine) |
| defects/crackseg_client.py | HTTP wrapper for 127.0.0.1:8092 |
| renders.py             | Open3D OffscreenRenderer for splat.png + path.png |
| scripts/probe_bag.py   | one-off iPad bag stream inspector |
| scripts/smoke_defect_tracker.py | end-to-end smoke test |

## Required GPU access

renders.py uses Open3D's OffscreenRenderer (Filament + EGL), which needs
the NVIDIA driver inside the container. Compose entry sets:

  NVIDIA_VISIBLE_DEVICES: all
  NVIDIA_DRIVER_CAPABILITIES: compute,utility,graphics
  deploy.resources.reservations.devices: [{driver: nvidia, count: 1, capabilities: [gpu]}]

See docker-compose.yml for the live config.
