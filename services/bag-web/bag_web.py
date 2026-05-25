"""bag-web — FastAPI server for browsing, uploading, and deleting rosbags
stored in gs://${GCS_BUCKET}. A "bag" is one top-level prefix in the bucket.
"""

import os
import secrets
import sys
from collections import defaultdict
from pathlib import PurePosixPath

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from google.cloud import storage


GCS_BUCKET = os.environ['GCS_BUCKET']
BAG_WEB_USER = os.environ.get('BAG_WEB_USER', '')
BAG_WEB_PASS = os.environ.get('BAG_WEB_PASS', '')

# Fail fast on partial config rather than running half-authenticated.
if bool(BAG_WEB_USER) != bool(BAG_WEB_PASS):
    print('FATAL: set BOTH BAG_WEB_USER and BAG_WEB_PASS, or neither.', file=sys.stderr)
    sys.exit(1)

AUTH_ENABLED = bool(BAG_WEB_USER)
if not AUTH_ENABLED:
    print('WARN: BAG_WEB_USER/BAG_WEB_PASS unset; running without authentication.',
          file=sys.stderr)

_basic = HTTPBasic(realm='atl4s-bag-web')


def require_auth(credentials: HTTPBasicCredentials = Depends(_basic)) -> str:
    # compare_digest avoids early-exit timing leaks.
    user_ok = secrets.compare_digest(credentials.username, BAG_WEB_USER)
    pass_ok = secrets.compare_digest(credentials.password, BAG_WEB_PASS)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='invalid credentials',
            headers={'WWW-Authenticate': 'Basic realm="atl4s-bag-web"'},
        )
    return credentials.username


def _noop() -> str:
    return 'anonymous'


auth_dep = require_auth if AUTH_ENABLED else _noop

app = FastAPI(title='ATL4S bag-web')
templates = Jinja2Templates(directory='templates')

_client: storage.Client | None = None


def bucket() -> storage.Bucket:
    global _client
    if _client is None:
        _client = storage.Client()
    return _client.bucket(GCS_BUCKET)


def _safe_bag_name(name: str) -> str:
    if not name or '/' in name or name in ('.', '..'):
        raise HTTPException(400, 'invalid bag name')
    return name


@app.get('/api/bags', dependencies=[Depends(auth_dep)])
def api_list_bags() -> list[dict]:
    bags: dict[str, dict] = defaultdict(lambda: {'size': 0, 'files': 0, 'updated': None})
    for blob in bucket().list_blobs():
        if '/' not in blob.name:
            continue  # bucket-root files aren't part of any bag
        prefix = blob.name.split('/', 1)[0]
        b = bags[prefix]
        b['size'] += blob.size or 0
        b['files'] += 1
        if blob.updated and (b['updated'] is None or blob.updated > b['updated']):
            b['updated'] = blob.updated

    out = []
    for name, info in bags.items():
        out.append({
            'name': name,
            'size_bytes': info['size'],
            'size_mib': round(info['size'] / 1024 / 1024, 2),
            'files': info['files'],
            'updated': info['updated'].isoformat() if info['updated'] else None,
        })
    out.sort(key=lambda b: b['updated'] or '', reverse=True)
    return out


@app.get('/api/bags/{bag_name}/files', dependencies=[Depends(auth_dep)])
def api_list_files(bag_name: str) -> list[dict]:
    _safe_bag_name(bag_name)
    prefix = f'{bag_name}/'
    files = []
    for blob in bucket().list_blobs(prefix=prefix):
        if blob.name == prefix:
            continue
        files.append({
            'name': blob.name[len(prefix):],
            'size_bytes': blob.size or 0,
            'updated': blob.updated.isoformat() if blob.updated else None,
        })
    if not files:
        raise HTTPException(404, f'bag {bag_name!r} not found')
    return files


@app.get('/api/bags/{bag_name}/files/{filename:path}', dependencies=[Depends(auth_dep)])
def api_download(bag_name: str, filename: str) -> StreamingResponse:
    _safe_bag_name(bag_name)
    rel = PurePosixPath(filename)
    if rel.is_absolute() or '..' in rel.parts:
        raise HTTPException(400, 'invalid filename')
    # get_blob() returns None on miss and populates size; blob() doesn't.
    blob = bucket().get_blob(f'{bag_name}/{rel.as_posix()}')
    if blob is None:
        raise HTTPException(404)

    def stream():
        with blob.open('rb') as fh:
            while chunk := fh.read(64 * 1024):
                yield chunk

    headers = {'Content-Disposition': f'attachment; filename="{rel.name}"'}
    if blob.size is not None:
        headers['Content-Length'] = str(blob.size)
    return StreamingResponse(stream(), media_type='application/octet-stream', headers=headers)


@app.post('/api/bags/{bag_name}/upload', dependencies=[Depends(auth_dep)])
async def api_upload(bag_name: str, files: list[UploadFile] = File(...)) -> dict:
    _safe_bag_name(bag_name)
    uploaded = []
    for f in files:
        if not f.filename:
            continue
        # upload_from_file iterates in chunks; combined with UploadFile's
        # SpooledTemporaryFile (spills to disk over ~1MB) multi-GB bags
        # stream end-to-end without holding the whole file in RAM.
        blob = bucket().blob(f'{bag_name}/{f.filename}')
        blob.upload_from_file(f.file, rewind=True)
        uploaded.append(f.filename)
    return {'bag': bag_name, 'uploaded': uploaded}


@app.delete('/api/bags/{bag_name}', dependencies=[Depends(auth_dep)])
def api_delete(bag_name: str) -> dict:
    _safe_bag_name(bag_name)
    prefix = f'{bag_name}/'
    deleted = 0
    for blob in bucket().list_blobs(prefix=prefix):
        blob.delete()
        deleted += 1
    if deleted == 0:
        raise HTTPException(404, f'bag {bag_name!r} not found')
    return {'bag': bag_name, 'deleted': deleted}


@app.get('/healthz')
def healthz() -> dict:
    # Unauthenticated by design — must not hit GCS so it's safe to call freely.
    return {'status': 'ok', 'bucket': GCS_BUCKET}


@app.get('/', response_class=HTMLResponse, dependencies=[Depends(auth_dep)])
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse('index.html', {
        'request': request,
        'bucket': GCS_BUCKET,
    })
