"""FastAPI app for the ATL4S dashboard.

Serves the React/Vite frontend and exposes ``/healthz``. Subsequent
commits add the rosbag-manager proxy under ``/api/*`` and the ROS topic
bridge under ``/ws/*``.
"""

import logging

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import auth
from backend.config import STATIC_DIR

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')

app = FastAPI(title='ATL4S dashboard')


@app.get('/healthz')
def healthz() -> dict:
    return {'status': 'ok'}


if (STATIC_DIR / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=str(STATIC_DIR / 'assets')), name='assets')


@app.get('/{path:path}', dependencies=[Depends(auth.require)])
def spa_fallback(path: str) -> FileResponse:
    target = STATIC_DIR / path
    if target.is_file():
        return FileResponse(str(target))
    return FileResponse(str(STATIC_DIR / 'index.html'))
