"""Upload endpoints + background watcher — pushes completed bags to GCS.

A bag is "completed" once nothing inside it has changed for STABLE_SECONDS;
this avoids racing in-flight recordings. A ``<bag>.uploaded`` sentinel file
sits next to each uploaded bag so restarts don't re-upload.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from google.cloud import storage

from app.config import BAG_DIR, GCS_BUCKET, POLL_SECONDS, STABLE_SECONDS

log = logging.getLogger('rosbag-manager.upload')

router = APIRouter(prefix='/api/uploads', tags=['uploads'])


def _safe_bag_name(name: str) -> str:
    if not name or '/' in name or name in ('.', '..'):
        raise HTTPException(400, 'invalid bag name')
    return name


def _iso(ts: Optional[float]) -> Optional[str]:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None


class Uploader:
    """Lazy GCS client + watcher task + per-bag in-flight set."""

    def __init__(self) -> None:
        self._client: Optional[storage.Client] = None
        self._in_flight: set[str] = set()
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def bucket(self) -> storage.Bucket:
        if self._client is None:
            self._client = storage.Client()
        return self._client.bucket(GCS_BUCKET)

    def _local_bags(self) -> list[Path]:
        BAG_DIR.mkdir(parents=True, exist_ok=True)
        return sorted(p for p in BAG_DIR.iterdir() if p.is_dir())

    def _summarize(self, bag: Path) -> dict:
        files = [p for p in bag.rglob('*') if p.is_file()]
        size = sum(p.stat().st_size for p in files)
        mtime = max((p.stat().st_mtime for p in files), default=None)
        sentinel = bag.parent / f'{bag.name}.uploaded'
        return {
            'name': bag.name,
            'size_bytes': size,
            'files': len(files),
            'mtime': _iso(mtime),
            'uploaded': sentinel.exists(),
            'in_flight': bag.name in self._in_flight,
        }

    def list_local(self) -> list[dict]:
        return [self._summarize(b) for b in self._local_bags()]

    async def upload_bag(self, bag: Path) -> int:
        sentinel = bag.parent / f'{bag.name}.uploaded'
        async with self._lock:
            if bag.name in self._in_flight:
                raise HTTPException(409, f'{bag.name} already uploading')
            if sentinel.exists():
                raise HTTPException(409, f'{bag.name} already uploaded')
            self._in_flight.add(bag.name)
        try:
            n = await asyncio.to_thread(self._upload_blocking, bag)
            sentinel.touch()
            log.info('uploaded %s (%d files)', bag.name, n)
            return n
        finally:
            async with self._lock:
                self._in_flight.discard(bag.name)

    def _upload_blocking(self, bag: Path) -> int:
        bucket = self.bucket()
        count = 0
        for path in bag.rglob('*'):
            if not path.is_file():
                continue
            blob_name = f'{bag.name}/{path.relative_to(bag).as_posix()}'
            blob = bucket.blob(blob_name)
            if blob.exists():
                log.info('skip %s (already in gs://%s/%s)', path.name, GCS_BUCKET, blob_name)
                continue
            log.info('upload %s → gs://%s/%s', path.name, GCS_BUCKET, blob_name)
            blob.upload_from_filename(str(path))
            count += 1
        return count

    async def _watch_loop(self) -> None:
        log.info('watching %s; bucket=%s (stable=%ds, poll=%ds)',
                 BAG_DIR, GCS_BUCKET, STABLE_SECONDS, POLL_SECONDS)
        while True:
            try:
                for bag in self._local_bags():
                    sentinel = bag.parent / f'{bag.name}.uploaded'
                    if sentinel.exists() or bag.name in self._in_flight:
                        continue
                    files = [p for p in bag.rglob('*') if p.is_file()]
                    if not files:
                        continue
                    age = time.time() - max(p.stat().st_mtime for p in files)
                    if age < STABLE_SECONDS:
                        continue
                    log.info('uploading %s (stable for %.0fs)', bag.name, age)
                    try:
                        await self.upload_bag(bag)
                    except HTTPException:
                        pass
                    except Exception:
                        log.exception('upload failed for %s', bag.name)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception('watcher iteration failed')
            await asyncio.sleep(POLL_SECONDS)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._watch_loop())

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


uploader = Uploader()


@router.get('')
def list_uploads() -> list[dict]:
    return uploader.list_local()


@router.post('/{bag_name}')
async def force_upload(bag_name: str) -> dict:
    _safe_bag_name(bag_name)
    bag = BAG_DIR / bag_name
    if not bag.is_dir():
        raise HTTPException(404, f'{bag_name} not found in {BAG_DIR}')
    n = await uploader.upload_bag(bag)
    return {'name': bag_name, 'files_uploaded': n}


async def on_startup() -> None:
    uploader.start()


async def on_shutdown() -> None:
    await uploader.stop()
