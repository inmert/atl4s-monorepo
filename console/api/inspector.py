"""Inspector proxy for the console (logic layer).

The inspector runs as a loopback-only backend container (model storage, and
later rosbag playback + GPU ML). The console is the single UI surface, so it
proxies the inspector's API under ``/api/inspector/*`` — keeping everything
same-origin (the three.js loader and uploads ride the session cookie) without
exposing the inspector port to browsers.

Streams in both directions so large model files (and uploads) don't buffer in
memory.
"""

import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from . import auth

INSPECTOR_URL = os.environ.get('INSPECTOR_URL', 'http://127.0.0.1:8091').rstrip('/')

router = APIRouter(prefix='/api/inspector', tags=['inspector'], dependencies=[Depends(auth.require)])

# Headers we must not copy back verbatim (httpx/Starlette set them per-stream).
_DROP_HEADERS = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}


async def _passthrough(method: str, path: str, request: Request) -> Response:
    """Stream a request to the inspector and stream its response back."""
    url = f'{INSPECTOR_URL}{path}'
    client = httpx.AsyncClient(timeout=None)
    # Forward the body as a stream only for write methods (covers multipart
    # uploads); preserve the content-type so the inspector parses the boundary.
    kwargs: dict = {}
    if method in ('POST', 'PUT', 'PATCH'):
        kwargs['content'] = request.stream()
        if 'content-type' in request.headers:
            kwargs['headers'] = {'content-type': request.headers['content-type']}
    try:
        req = client.build_request(method, url, **kwargs)
        upstream = await client.send(req, stream=True)
    except httpx.ConnectError:
        await client.aclose()
        raise HTTPException(502, detail='inspector service unavailable')

    async def body():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    out_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _DROP_HEADERS}
    return StreamingResponse(body(), status_code=upstream.status_code, headers=out_headers)


@router.get('/models')
async def list_models(request: Request) -> Response:
    return await _passthrough('GET', '/api/models', request)


@router.post('/models')
async def upload_model(request: Request) -> Response:
    return await _passthrough('POST', '/api/models', request)


@router.get('/models/{name}/file')
async def model_file(name: str, request: Request) -> Response:
    return await _passthrough('GET', f'/api/models/{quote(name, safe="")}/file', request)


@router.delete('/models/{name}')
async def delete_model(name: str, request: Request) -> Response:
    return await _passthrough('DELETE', f'/api/models/{quote(name, safe="")}', request)


# --- Rosbags ----------------------------------------------------------------

@router.get('/rosbags')
async def rosbags(request: Request) -> Response:
    return await _passthrough('GET', '/api/rosbags', request)


@router.get('/rosbags/status')
async def rosbag_status(request: Request) -> Response:
    return await _passthrough('GET', '/api/rosbags/status', request)


@router.get('/rosbags/{name}/metadata')
async def rosbag_metadata(name: str, request: Request) -> Response:
    return await _passthrough('GET', f'/api/rosbags/{quote(name, safe="")}/metadata', request)


@router.post('/rosbags/{name}/play')
async def rosbag_play(name: str, request: Request) -> Response:
    return await _passthrough('POST', f'/api/rosbags/{quote(name, safe="")}/play', request)


@router.post('/rosbags/stop')
async def rosbag_stop(request: Request) -> Response:
    return await _passthrough('POST', '/api/rosbags/stop', request)


@router.get('/ml/pipelines')
async def ml_pipelines(request: Request) -> Response:
    return await _passthrough('GET', '/api/ml/pipelines', request)
