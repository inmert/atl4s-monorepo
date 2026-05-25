"""GCS browser endpoints — list / files / download / multipart upload / delete.

Operates on bags stored as top-level prefixes in ``gs://${GCS_BUCKET}``.
Ported from the old bag-web service; the security boundary is the loopback
bind, so per-route auth is intentionally absent.
"""

from collections import defaultdict
from pathlib import PurePosixPath

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.clients import bucket
from app.util import safe_bag_name

router = APIRouter(prefix='/api/bags', tags=['bags'])


@router.get('')
def list_bags() -> list[dict]:
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

    out = [
        {
            'name': name,
            'size_bytes': info['size'],
            'size_mib': round(info['size'] / 1024 / 1024, 2),
            'files': info['files'],
            'updated': info['updated'].isoformat() if info['updated'] else None,
        }
        for name, info in bags.items()
    ]
    out.sort(key=lambda b: b['updated'] or '', reverse=True)
    return out


@router.get('/{bag_name}/files')
def list_files(bag_name: str) -> list[dict]:
    safe_bag_name(bag_name)
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


@router.get('/{bag_name}/files/{filename:path}')
def download(bag_name: str, filename: str) -> StreamingResponse:
    safe_bag_name(bag_name)
    rel = PurePosixPath(filename)
    if rel.is_absolute() or '..' in rel.parts:
        raise HTTPException(400, 'invalid filename')
    # get_blob() populates size+metadata; blob() returns an unverified handle.
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


@router.post('/{bag_name}/upload')
async def upload(bag_name: str, files: list[UploadFile] = File(...)) -> dict:
    safe_bag_name(bag_name)
    uploaded = []
    for f in files:
        if not f.filename:
            continue
        # UploadFile's SpooledTemporaryFile spills to disk over ~1MB, so
        # multi-GB bags stream end-to-end without holding the file in RAM.
        blob = bucket().blob(f'{bag_name}/{f.filename}')
        blob.upload_from_file(f.file, rewind=True)
        uploaded.append(f.filename)
    return {'bag': bag_name, 'uploaded': uploaded}


@router.delete('/{bag_name}')
def delete(bag_name: str) -> dict:
    safe_bag_name(bag_name)
    prefix = f'{bag_name}/'
    deleted = 0
    for blob in bucket().list_blobs(prefix=prefix):
        blob.delete()
        deleted += 1
    if deleted == 0:
        raise HTTPException(404, f'bag {bag_name!r} not found')
    return {'bag': bag_name, 'deleted': deleted}
