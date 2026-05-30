"""FastAPI backend for the ATL4S inspector (engine).

Stores + serves uploaded 3D models and exposes placeholder endpoints for rosbag
playback and live ML pipelines. The UI lives in the console (which proxies to
this service under /api/inspector/*); this process serves no SPA of its own.
"""

import os
import re
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.config import ALLOWED_EXT, MODELS_DIR, ROSBAG_MANAGER_URL

app = FastAPI(title='ATL4S Inspector')


def _safe_name(name: str) -> str:
    """Strip any path and reduce to a filesystem-safe basename."""
    base = os.path.basename(name or '')
    base = re.sub(r'[^A-Za-z0-9._-]', '_', base).strip('._')
    return base or 'model'


def _model_info(p: Path) -> dict:
    st = p.stat()
    return {
        'name': p.name,
        'ext': p.suffix.lower().lstrip('.'),
        'size_bytes': st.st_size,
        'modified': st.st_mtime,
    }


def _resolve(name: str) -> Path:
    """Resolve a model path, guarding against traversal outside MODELS_DIR."""
    p = (MODELS_DIR / _safe_name(name)).resolve()
    root = MODELS_DIR.resolve()
    if root != p.parent or not p.is_file():
        raise HTTPException(404, detail='model not found')
    return p


@app.get('/healthz')
def healthz() -> dict:
    return {'status': 'ok'}


@app.get('/api/models')
def list_models() -> dict:
    if not MODELS_DIR.is_dir():
        return {'models': []}
    models = [
        _model_info(p)
        for p in sorted(MODELS_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in ALLOWED_EXT
    ]
    return {'models': models, 'allowed_ext': sorted(e.lstrip('.') for e in ALLOWED_EXT)}


@app.post('/api/models')
async def upload_model(file: UploadFile = File(...)) -> dict:
    name = _safe_name(file.filename or 'model')
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, detail=f'unsupported type "{ext}". Allowed: {sorted(ALLOWED_EXT)}')
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODELS_DIR / name
    # Stream to disk in chunks so large models don't sit in memory.
    with dest.open('wb') as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)
    return _model_info(dest)


@app.get('/api/models/{name}/file')
def get_model_file(name: str) -> FileResponse:
    return FileResponse(str(_resolve(name)), media_type='application/octet-stream')


@app.delete('/api/models/{name}')
def delete_model(name: str) -> dict:
    _resolve(name).unlink()
    return {'deleted': _safe_name(name)}


# --- Rosbags (delegated to rosbag-manager for now) --------------------------

async def _rbm(method: str, path: str, **kwargs):
    """Call rosbag-manager and bubble up its JSON / errors."""
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            r = await client.request(method, f'{ROSBAG_MANAGER_URL}{path}', **kwargs)
        except httpx.HTTPError:
            raise HTTPException(502, detail='rosbag-manager unavailable')
    if r.status_code >= 400:
        try:
            detail = r.json().get('detail', r.text)
        except Exception:
            detail = r.text
        raise HTTPException(r.status_code, detail=detail)
    return r.json()


@app.get('/api/rosbags')
async def list_rosbags() -> dict:
    bags = await _rbm('GET', '/api/bags')
    return {'supported': True, 'bags': bags}


@app.get('/api/rosbags/status')
async def rosbag_status() -> dict:
    return await _rbm('GET', '/api/replay/status')


@app.get('/api/rosbags/{name}/metadata')
async def rosbag_metadata(name: str) -> dict:
    return await _rbm('GET', f'/api/bags/{quote(name, safe="")}/metadata')


@app.post('/api/rosbags/{name}/play')
async def rosbag_play(name: str) -> dict:
    return await _rbm('POST', '/api/replay/start', json={'bag': name})


@app.post('/api/rosbags/stop')
async def rosbag_stop() -> dict:
    return await _rbm('POST', '/api/replay/stop')


@app.get('/api/ml/pipelines')
def ml_pipelines() -> dict:
    # Will advertise pipelines that can run live on the current model / rosbag.
    return {
        'supported': False,
        'pipelines': [],
        'message': 'Live ML pipelines will be integrated here, applied to the model or rosbag in view.',
    }
