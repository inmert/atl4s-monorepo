"""FastAPI app exposing bag-plane operations on 127.0.0.1:8086.

Records, watches and uploads to GCS, browses GCS, and replays via
``ros2 bag play``. Per-feature modules expose a router plus optional
lifespan hooks; this module composes them. GCS browser and replay land
in subsequent commits.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import BAG_DIR, GCS_BUCKET
from app.gcs import router as gcs_router
from app.record import on_shutdown as record_shutdown
from app.record import router as record_router
from app.replay import on_shutdown as replay_shutdown
from app.replay import router as replay_router
from app.upload import on_shutdown as upload_shutdown
from app.upload import on_startup as upload_startup
from app.upload import router as upload_router

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')


@asynccontextmanager
async def lifespan(app: FastAPI):
    await upload_startup()
    try:
        yield
    finally:
        await record_shutdown()
        await replay_shutdown()
        await upload_shutdown()


app = FastAPI(title='ATL4S rosbag-manager', lifespan=lifespan)
app.include_router(record_router)
app.include_router(upload_router)
app.include_router(gcs_router)
app.include_router(replay_router)


@app.get('/healthz')
def healthz() -> dict:
    return {'status': 'ok', 'bag_dir': str(BAG_DIR), 'bucket': GCS_BUCKET}
