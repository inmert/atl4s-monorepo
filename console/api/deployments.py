"""Deployment registry for the console (logic layer).

Tracks robots / vehicles / sensors (simulator or real) and their connection
settings (protocol + host + port). CRUD-backed by a YAML file under
console/config/, so edits made on the Deployments page persist across restarts.

Status is derived per request, never stored: a simulator deployment is Online
when its linked containers are running (reusing the Docker service); real
deployments report Offline until live connectivity probing exists.
"""

import logging
import os
import re
import tempfile
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import auth
from .containers import service as docker_service

log = logging.getLogger('console.deployments')

# Defaults to console/config/deployments.yaml; override with DEPLOYMENTS_CONFIG.
CONFIG_PATH = Path(
    os.environ.get('DEPLOYMENTS_CONFIG')
    or (Path(__file__).resolve().parents[1] / 'config' / 'deployments.yaml')
)

# Sets of supported values. Kept small and extended deliberately as new support
# lands; the list endpoint echoes these so the UI form stays in sync.
TYPES = ('drone', 'rover', 'sensor')
MODES = ('simulator', 'real')
PROTOCOLS = ('mavlink',)


class DeploymentInput(BaseModel):
    name: str
    type: str
    mode: str
    protocol: str = 'mavlink'
    host: str = ''
    port: int = 14550
    description: str = ''
    containers: list[str] = Field(default_factory=list)
    telemetry: dict[str, str] = Field(default_factory=dict)

    @field_validator('name')
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('name is required')
        return v

    @field_validator('type')
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in TYPES:
            raise ValueError(f'type must be one of {list(TYPES)}')
        return v

    @field_validator('mode')
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in MODES:
            raise ValueError(f'mode must be one of {list(MODES)}')
        return v

    @field_validator('protocol')
    @classmethod
    def _protocol(cls, v: str) -> str:
        if v not in PROTOCOLS:
            raise ValueError(f'protocol must be one of {list(PROTOCOLS)} (more coming later)')
        return v

    @field_validator('port')
    @classmethod
    def _port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError('port must be between 1 and 65535')
        return v

    @field_validator('containers')
    @classmethod
    def _containers(cls, v: list[str]) -> list[str]:
        return [c.strip() for c in v if c and c.strip()]


def _slug(name: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return s or 'deployment'


class Registry:
    """Reads/writes the YAML registry. Reloads before every mutation so an
    external edit to the file isn't clobbered, and writes atomically."""

    def __init__(self) -> None:
        self._items: list[dict] = []

    def load(self) -> list[dict]:
        if not CONFIG_PATH.is_file():
            self._items = []
            return self._items
        raw = yaml.safe_load(CONFIG_PATH.read_text()) or []
        if not isinstance(raw, list):
            raise HTTPException(500, detail=f'{CONFIG_PATH.name} must be a YAML list')
        self._items = raw
        return self._items

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(CONFIG_PATH.parent), suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                yaml.safe_dump(self._items, f, sort_keys=False, default_flow_style=False)
            # mkstemp creates 0600; the container writes as root, so widen to
            # 0644 or the host user (and git) can't read the bind-mounted file.
            os.chmod(tmp, 0o644)
            os.replace(tmp, CONFIG_PATH)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def all(self) -> list[dict]:
        return list(self.load())

    def get(self, dep_id: str) -> dict | None:
        return next((d for d in self.load() if d.get('id') == dep_id), None)

    def exists(self, dep_id: str) -> bool:
        return self.get(dep_id) is not None

    def add(self, item: dict) -> None:
        self.load()
        self._items.append(item)
        self.save()

    def update(self, dep_id: str, item: dict) -> None:
        self.load()
        for i, d in enumerate(self._items):
            if d.get('id') == dep_id:
                self._items[i] = item
                self.save()
                return
        raise KeyError(dep_id)

    def delete(self, dep_id: str) -> None:
        self.load()
        kept = [d for d in self._items if d.get('id') != dep_id]
        if len(kept) == len(self._items):
            raise KeyError(dep_id)
        self._items = kept
        self.save()


registry = Registry()


def _running_containers() -> set:
    try:
        return {c['name'] for c in docker_service.list_summaries() if c['state'] == 'running'}
    except Exception:
        return set()


def _with_status(item: dict, running: set) -> dict:
    out = {
        'id': item.get('id'),
        'name': item.get('name'),
        'type': item.get('type'),
        'mode': item.get('mode'),
        'protocol': item.get('protocol', 'mavlink'),
        'host': item.get('host', '') or '',
        'port': item.get('port'),
        'description': item.get('description', '') or '',
        'containers': item.get('containers') or [],
        'telemetry': item.get('telemetry') or {},
    }
    containers = out['containers']
    if out['mode'] == 'simulator' and containers:
        up = sum(1 for c in containers if c in running)
        out['status'] = 'online' if up == len(containers) else 'offline' if up == 0 else 'degraded'
    else:
        # Real deployments have no liveness probe yet; report Offline honestly.
        out['status'] = 'offline'
    return out


router = APIRouter(prefix='/api/deployments', tags=['deployments'])


@router.get('', dependencies=[Depends(auth.require)])
def list_deployments() -> dict:
    running = _running_containers()
    return {
        'deployments': [_with_status(d, running) for d in registry.all()],
        # Echoed so the UI form offers exactly what the backend supports.
        'options': {'types': list(TYPES), 'modes': list(MODES), 'protocols': list(PROTOCOLS)},
    }


@router.get('/{dep_id}', dependencies=[Depends(auth.require)])
def get_deployment(dep_id: str) -> dict:
    item = registry.get(dep_id)
    if item is None:
        raise HTTPException(404, detail=f'unknown deployment "{dep_id}"')
    return _with_status(item, _running_containers())


@router.post('', dependencies=[Depends(auth.require)])
def create_deployment(body: DeploymentInput) -> dict:
    base = _slug(body.name)
    dep_id, n = base, 2
    while registry.exists(dep_id):
        dep_id, n = f'{base}-{n}', n + 1
    item = {'id': dep_id, **body.model_dump()}
    registry.add(item)
    log.info('deployment created: %s', dep_id)
    return _with_status(item, _running_containers())


@router.put('/{dep_id}', dependencies=[Depends(auth.require)])
def update_deployment(dep_id: str, body: DeploymentInput) -> dict:
    if not registry.exists(dep_id):
        raise HTTPException(404, detail=f'unknown deployment "{dep_id}"')
    item = {'id': dep_id, **body.model_dump()}
    registry.update(dep_id, item)
    log.info('deployment updated: %s', dep_id)
    return _with_status(item, _running_containers())


@router.delete('/{dep_id}', dependencies=[Depends(auth.require)])
def delete_deployment(dep_id: str) -> dict:
    try:
        registry.delete(dep_id)
    except KeyError:
        raise HTTPException(404, detail=f'unknown deployment "{dep_id}"')
    log.info('deployment deleted: %s', dep_id)
    return {'deleted': dep_id}
