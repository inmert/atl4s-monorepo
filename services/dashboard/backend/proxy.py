"""Proxy layer — forwards bag-plane requests to rosbag-manager.

All routes under ``/api/*`` are gated by HTTP Basic at the dashboard edge.
The proxy uses httpx in streaming mode so multi-GB bag downloads and
multipart uploads don't buffer in memory.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from backend import auth
from backend.config import ROSBAG_MANAGER_URL

log = logging.getLogger('dashboard.proxy')

# Hop-by-hop headers should not be forwarded across the proxy boundary.
_HOP_BY_HOP = {
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'transfer-encoding', 'upgrade', 'content-encoding',
}

_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan():
    global _client
    _client = httpx.AsyncClient(
        base_url=ROSBAG_MANAGER_URL,
        timeout=httpx.Timeout(30.0, read=None),
    )
    log.info('proxy upstream=%s', ROSBAG_MANAGER_URL)
    try:
        yield
    finally:
        await _client.aclose()
        _client = None


router = APIRouter(prefix='/api', tags=['proxy'])


@router.api_route('/{path:path}',
                  methods=['GET', 'POST', 'PUT', 'DELETE'],
                  dependencies=[Depends(auth.require)])
async def proxy(path: str, request: Request) -> StreamingResponse:
    if _client is None:
        raise RuntimeError('proxy client not initialized')

    req_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != 'host'
    }

    upstream_req = _client.build_request(
        method=request.method,
        url=f'/api/{path}',
        params=request.query_params,
        headers=req_headers,
        content=request.stream(),
    )
    upstream = await _client.send(upstream_req, stream=True)

    resp_headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }

    return StreamingResponse(
        upstream.aiter_raw(),
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=upstream.headers.get('content-type'),
        background=BackgroundTask(upstream.aclose),
    )
