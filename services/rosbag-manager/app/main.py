"""FastAPI app exposing bag-plane operations on 127.0.0.1:8086.

Records, watches and uploads to GCS, browses GCS, and replays via
``ros2 bag play``. Per-feature modules are mounted as routers; subsequent
commits add upload, gcs, and replay alongside record.
"""

from fastapi import FastAPI

from app.config import BAG_DIR, GCS_BUCKET
from app.record import router as record_router

app = FastAPI(title='ATL4S rosbag-manager')
app.include_router(record_router)


@app.get('/healthz')
def healthz() -> dict:
    return {'status': 'ok', 'bag_dir': str(BAG_DIR), 'bucket': GCS_BUCKET}
