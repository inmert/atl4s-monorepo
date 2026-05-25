"""Replay endpoints — downloads a bag from GCS and runs ``ros2 bag play``."""

import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.clients import bucket
from app.config import GCS_BUCKET, REPLAY_DIR
from app.util import safe_bag_name

log = logging.getLogger('rosbag-manager.replay')

router = APIRouter(prefix='/api/replay', tags=['replay'])


class StartRequest(BaseModel):
    bag: str


class Replayer:
    """Owns the single active replay — download + ros2 bag play subprocess."""

    def __init__(self) -> None:
        self.state: str = 'idle'  # 'idle' | 'downloading' | 'playing' | 'stopping'
        self.bag: Optional[str] = None
        self.started_at: Optional[str] = None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def status(self) -> dict:
        return {'state': self.state, 'bag': self.bag, 'started_at': self.started_at}

    async def start(self, bag: str) -> dict:
        safe_bag_name(bag)
        async with self._lock:
            if self.state != 'idle':
                raise HTTPException(409, f'already {self.state}')

            has_metadata = await asyncio.to_thread(
                lambda: bucket().blob(f'{bag}/metadata.yaml').exists()
            )
            if not has_metadata:
                raise HTTPException(404, f'bag {bag!r} not found in gs://{GCS_BUCKET}')

            self.bag = bag
            self.state = 'downloading'
            self.started_at = datetime.now(timezone.utc).isoformat()
            self._task = asyncio.create_task(self._run(bag))
        return self.status()

    async def stop(self) -> dict:
        async with self._lock:
            if self.state == 'idle':
                raise HTTPException(409, 'not replaying')
            self.state = 'stopping'
            proc = self._proc
            task = self._task

        if proc is not None:
            proc.terminate()
        elif task is not None:
            task.cancel()

        if task is not None:
            try:
                await task
            except asyncio.CancelledError:
                pass
        return self.status()

    async def _run(self, bag: str) -> None:
        play_dir = REPLAY_DIR / bag
        try:
            await asyncio.to_thread(self._download_blocking, bag, play_dir)
            async with self._lock:
                if self.state == 'stopping':
                    return
                self.state = 'playing'
                self._proc = await asyncio.create_subprocess_exec(
                    'ros2', 'bag', 'play', str(play_dir),
                )
            await self._proc.wait()
        except asyncio.CancelledError:
            log.info('replay task cancelled (bag=%s)', bag)
        except Exception:
            log.exception('replay failed for %s', bag)
        finally:
            await asyncio.to_thread(shutil.rmtree, play_dir, ignore_errors=True)
            async with self._lock:
                self._proc = None
                self._task = None
                self.state = 'idle'
                self.bag = None
                self.started_at = None

    def _download_blocking(self, bag: str, dest: Path) -> None:
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True, exist_ok=True)
        b = bucket()
        for blob in b.list_blobs(prefix=f'{bag}/'):
            if blob.name.endswith('/'):
                continue
            local_path = dest / blob.name[len(bag) + 1:]
            local_path.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(local_path))
            log.info('downloaded gs://%s/%s → %s', GCS_BUCKET, blob.name, local_path)


replayer = Replayer()


@router.post('/start')
async def start(req: StartRequest) -> dict:
    return await replayer.start(req.bag)


@router.post('/stop')
async def stop() -> dict:
    return await replayer.stop()


@router.get('/status')
def status() -> dict:
    return replayer.status()


async def on_shutdown() -> None:
    if replayer.state != 'idle':
        log.info('shutdown: stopping active replay')
        try:
            await replayer.stop()
        except HTTPException:
            pass
