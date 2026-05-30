"""CrackSeg proxy for the console (logic layer).

The crackseg container is a loopback-only GPU inference backend. The console
exposes it under /api/crackseg so the inspector can run it on the rendered frame
(same-origin, session-gated) and knows whether it's running (to enable the
overlay toggle).
"""

import os

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from . import auth
from .containers import service as docker_service

CRACKSEG_URL = os.environ.get('CRACKSEG_URL', 'http://127.0.0.1:8092').rstrip('/')
CRACKSEG_CONTAINER = os.environ.get('CRACKSEG_CONTAINER', 'atl4s-crackseg')

router = APIRouter(prefix='/api/crackseg', tags=['crackseg'], dependencies=[Depends(auth.require)])


def _running() -> bool:
    try:
        return any(
            c['name'] == CRACKSEG_CONTAINER and c['state'] == 'running'
            for c in docker_service.list_summaries()
        )
    except Exception:
        return False


@router.get('/info')
async def info() -> dict:
    if not _running():
        return {'running': False}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f'{CRACKSEG_URL}/info')
        data = r.json()
        return {'running': True, **(data if isinstance(data, dict) else {})}
    except Exception:
        # Container is up but the model may still be loading.
        return {'running': True, 'status': 'starting'}


@router.post('/infer')
async def infer(request: Request) -> Response:
    if not _running():
        return JSONResponse({'detail': 'crackseg is not running'}, status_code=409)
    data = await request.body()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f'{CRACKSEG_URL}/infer',
                content=data,
                headers={'content-type': request.headers.get('content-type', 'application/octet-stream')},
            )
    except httpx.HTTPError:
        return JSONResponse({'detail': 'crackseg unavailable'}, status_code=502)
    return Response(content=r.content, status_code=r.status_code,
                    media_type=r.headers.get('content-type', 'image/png'))
