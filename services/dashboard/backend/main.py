"""FastAPI app for the ATL4S dashboard.

Serves the React/Vite frontend, exposes ``/healthz``, and proxies
bag-plane operations to rosbag-manager under ``/api/*``. The ROS topic
bridge under ``/ws/*`` lands in a subsequent commit.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import auth, proxy
from backend.config import STATIC_DIR

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with proxy.lifespan():
        yield


app = FastAPI(title='ATL4S dashboard', lifespan=lifespan)


@app.get('/healthz')
def healthz() -> dict:
    return {'status': 'ok'}


app.include_router(proxy.router)


if (STATIC_DIR / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=str(STATIC_DIR / 'assets')), name='assets')


@app.get('/{path:path}', dependencies=[Depends(auth.require)])
def spa_fallback(path: str) -> FileResponse:
    target = STATIC_DIR / path
    if target.is_file():
        return FileResponse(str(target))
    return FileResponse(str(STATIC_DIR / 'index.html'))
