"""FastAPI app exposing bag-plane operations on 127.0.0.1:8086.

Records, watches and uploads to GCS, browses GCS, and replays via
``ros2 bag play``. Subsequent commits add the per-feature routers under
``app/`` (record, upload, gcs, replay); this scaffold ships /healthz only.
"""

from fastapi import FastAPI

from app.config import BAG_DIR, GCS_BUCKET

app = FastAPI(title='ATL4S rosbag-manager')


@app.get('/healthz')
def healthz() -> dict:
    return {'status': 'ok', 'bag_dir': str(BAG_DIR), 'bucket': GCS_BUCKET}
