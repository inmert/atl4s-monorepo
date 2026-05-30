"""ATL4S CrackSeg — crack-segmentation inference service.

Loopback-only backend (the console proxies to it). The console Pipelines page
starts/stops/configures this container; when it's running, the inspector sends
the rendered frame to /infer and overlays the returned crack mask.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from app.infer import Engine

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('crackseg.main')

app = FastAPI(title='ATL4S CrackSeg')
engine: Engine | None = None


@app.on_event('startup')
def _startup() -> None:
    global engine
    engine = Engine()


@app.get('/healthz')
def healthz() -> dict:
    return {'status': 'ok' if engine is not None else 'loading'}


@app.get('/info')
def info() -> dict:
    return engine.info() if engine is not None else {'status': 'loading'}


@app.post('/infer')
async def infer(request: Request):
    if engine is None:
        return JSONResponse({'detail': 'model still loading'}, status_code=503)
    data = await request.body()
    if not data:
        return JSONResponse({'detail': 'empty image body'}, status_code=400)
    png = await run_in_threadpool(engine.infer_png, data)
    return Response(content=png, media_type='image/png')
