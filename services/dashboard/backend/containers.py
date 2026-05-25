"""Container introspection — talks to the Docker daemon via the bind-mounted
``/var/run/docker.sock`` and reports per-container state for the dashboard's
Health page.

Filters by the ``atl4s-`` name prefix so the dashboard surfaces only its own
stack, not anything else running on the host.
"""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import docker
from fastapi import APIRouter, Depends, HTTPException

from backend import auth

log = logging.getLogger('dashboard.containers')

NAME_PREFIX = os.environ.get('CONTAINERS_NAME_PREFIX', 'atl4s-')

# Map docker container state → dashboard severity level. "running" with no
# health check (most of our containers) is OK; only a failing health check
# or a non-running state degrades.
_STATE_LEVEL = {
    'running': 'ok',
    'restarting': 'warn',
    'paused': 'warn',
    'created': 'warn',
    'exited': 'err',
    'dead': 'err',
    'removing': 'warn',
}

_HEALTH_LEVEL = {
    'healthy': 'ok',
    'starting': 'warn',
    'unhealthy': 'err',
}


class ContainerInspector:
    def __init__(self) -> None:
        self._client: Optional[docker.DockerClient] = None
        self._error: Optional[str] = None

    def connect(self) -> None:
        try:
            self._client = docker.from_env()
            # Force a round-trip so we surface unreachable-socket errors at
            # startup, not on the first /api/containers call.
            self._client.ping()
            log.info('connected to docker daemon')
        except Exception as exc:  # docker.errors.DockerException + child variants
            self._client = None
            self._error = str(exc)
            log.warning('docker unavailable: %s', exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def error(self) -> Optional[str]:
        return self._error

    def list(self) -> list[dict]:
        if self._client is None:
            return []
        try:
            containers = self._client.containers.list(
                all=True, filters={'name': NAME_PREFIX}
            )
        except Exception:
            log.exception('docker list failed')
            return []
        return [self._summary(c) for c in containers]

    @staticmethod
    def _summary(c) -> dict:
        attrs = c.attrs
        state = attrs.get('State', {}) or {}
        config = attrs.get('Config', {}) or {}
        status = state.get('Status', 'unknown')
        health_status = (state.get('Health') or {}).get('Status')
        started_at = state.get('StartedAt') or None

        uptime_sec: Optional[float] = None
        if status == 'running' and started_at:
            # Docker returns ISO8601 with nanosecond precision; Python <3.11
            # fromisoformat only accepts up to microseconds. Truncate the
            # fractional part to 6 digits.
            iso = re.sub(r'\.(\d{6})\d+', r'.\1', started_at).replace('Z', '+00:00')
            try:
                dt = datetime.fromisoformat(iso)
                uptime_sec = (datetime.now(timezone.utc) - dt).total_seconds()
            except ValueError:
                uptime_sec = None

        level = _STATE_LEVEL.get(status, 'warn')
        if health_status is not None:
            level = _HEALTH_LEVEL.get(health_status, level)

        return {
            'name': c.name,
            'state': status,
            'health': health_status,
            'level': level,
            'started_at': started_at,
            'uptime_sec': uptime_sec,
            'image': config.get('Image'),
            'restart_count': attrs.get('RestartCount', 0),
        }


inspector = ContainerInspector()


router = APIRouter(prefix='/api/containers', tags=['containers'])


@router.get('', dependencies=[Depends(auth.require)])
def list_containers() -> dict:
    if not inspector.available:
        raise HTTPException(
            status_code=503,
            detail=f'docker socket unavailable: {inspector.error or "not configured"}',
        )
    return {'containers': inspector.list()}
