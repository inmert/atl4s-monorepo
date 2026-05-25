"""Record endpoints — manages a single ``ros2 bag record`` subprocess."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import BAG_DIR, DEFAULT_RECORD_TOPICS
from app.util import safe_bag_name

log = logging.getLogger('rosbag-manager.record')

router = APIRouter(prefix='/api/record', tags=['record'])


class StartRequest(BaseModel):
    name: Optional[str] = None
    topics: Optional[list[str]] = None
    duration: Optional[float] = None


def _qos_overrides_yaml(topics: list[str]) -> str:
    # ros2 bag record subscribes Reliable by default; without per-topic
    # overrides every Best Effort publisher (most of /mavros/*) is silently
    # missed. Humble's parser accepts `topic: <dict>` but crashes on the
    # more common `topic: [<dict>]` list form.
    return ''.join(
        f'{t}:\n'
        '  history: keep_last\n'
        '  depth: 100\n'
        '  reliability: best_effort\n'
        '  durability: volatile\n'
        for t in topics
    )


class Recorder:
    """Owns the single active record subprocess and its metadata."""

    def __init__(self) -> None:
        self.state: str = 'idle'  # 'idle' | 'recording' | 'stopping'
        self.name: Optional[str] = None
        self.topics: Optional[list[str]] = None
        self.output: Optional[Path] = None
        self.started_at: Optional[str] = None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._auto_stop_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def status(self) -> dict:
        return {
            'state': self.state,
            'name': self.name,
            'topics': self.topics,
            'output': str(self.output) if self.output else None,
            'started_at': self.started_at,
        }

    async def start(self, name: Optional[str], topics: Optional[list[str]],
                    duration: Optional[float]) -> dict:
        async with self._lock:
            if self.state != 'idle':
                raise HTTPException(409, f'already {self.state}')

            name = safe_bag_name(
                name or f'atl4s-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}'
            )
            topics = topics or DEFAULT_RECORD_TOPICS
            if not topics:
                raise HTTPException(400, 'no topics to record')

            BAG_DIR.mkdir(parents=True, exist_ok=True)
            output = BAG_DIR / name
            if output.exists():
                raise HTTPException(409, f'bag {name!r} already exists at {output}')

            qos_path = Path('/tmp') / f'qos-{name}.yaml'
            qos_path.write_text(_qos_overrides_yaml(topics))

            cmd = [
                'ros2', 'bag', 'record',
                '--output', str(output),
                '--storage', 'mcap',
                '--qos-profile-overrides-path', str(qos_path),
                *topics,
            ]
            log.info('starting: %s', ' '.join(cmd))
            self._proc = await asyncio.create_subprocess_exec(*cmd)

            self.state = 'recording'
            self.name = name
            self.topics = topics
            self.output = output
            self.started_at = datetime.now(timezone.utc).isoformat()
            asyncio.create_task(self._monitor(self._proc))
            if duration is not None:
                self._auto_stop_task = asyncio.create_task(self._auto_stop(duration))

            return self.status()

    async def stop(self) -> dict:
        async with self._lock:
            if self.state != 'recording':
                raise HTTPException(409, f'not recording (state={self.state})')
            proc = self._proc
            self.state = 'stopping'
            if proc is not None:
                proc.terminate()

        if proc is not None:
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                log.warning('SIGTERM timed out; sending SIGKILL')
                proc.kill()
                await proc.wait()
        return self.status()

    async def _monitor(self, proc: asyncio.subprocess.Process) -> None:
        rc = await proc.wait()
        log.info('record subprocess exited rc=%d', rc)
        async with self._lock:
            if self._proc is proc:
                self._proc = None
                self.state = 'idle'
                self.name = None
                self.topics = None
                self.output = None
                self.started_at = None
            task = self._auto_stop_task
            self._auto_stop_task = None
        if task is not None and not task.done():
            task.cancel()

    async def _auto_stop(self, duration: float) -> None:
        try:
            await asyncio.sleep(duration)
        except asyncio.CancelledError:
            return
        if self.state == 'recording':
            try:
                await self.stop()
            except HTTPException:
                pass


recorder = Recorder()


@router.post('/start')
async def start(req: StartRequest) -> dict:
    return await recorder.start(req.name, req.topics, req.duration)


@router.post('/stop')
async def stop() -> dict:
    return await recorder.stop()


@router.get('/status')
def status() -> dict:
    return recorder.status()


async def on_shutdown() -> None:
    if recorder.state == 'recording':
        log.info('shutdown: stopping active recording')
        try:
            await recorder.stop()
        except HTTPException:
            pass
