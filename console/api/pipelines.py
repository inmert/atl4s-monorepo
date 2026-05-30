"""Pipeline registry for the console (logic layer).

Lists pipeline services (registry: console/config/pipelines.yaml), reports each
one's container status, exposes a schema-driven config form, persists config to
console/config/pipelines/{id}.yaml (merging so keys outside the form survive),
and starts/stops/restarts the container via the Docker socket. Restart applies
config (the containers read it at startup, like perception-lidar / crackseg).
"""

import logging
import os
import tempfile
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import auth
from .containers import service as docker_service

log = logging.getLogger('console.pipelines')

CONFIG_DIR = Path(os.environ.get('PIPELINES_CONFIG_DIR') or (Path(__file__).resolve().parents[1] / 'config'))
REGISTRY_PATH = CONFIG_DIR / 'pipelines.yaml'

ACTIONS = {'start', 'stop', 'restart'}


class ConfigBody(BaseModel):
    config: dict


def _registry() -> list[dict]:
    if not REGISTRY_PATH.is_file():
        return []
    data = yaml.safe_load(REGISTRY_PATH.read_text()) or []
    if not isinstance(data, list):
        raise HTTPException(500, detail='pipelines.yaml must be a YAML list')
    return data


def _entry(pid: str) -> dict:
    entry = next((p for p in _registry() if p.get('id') == pid), None)
    if entry is None:
        raise HTTPException(404, detail=f'unknown pipeline "{pid}"')
    return entry


def _config_path(entry: dict) -> Path:
    return CONFIG_DIR / entry.get('config_file', f'pipelines/{entry["id"]}.yaml')


def _read_config(entry: dict) -> dict:
    path = _config_path(entry)
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text()) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _container_states() -> dict:
    try:
        return {c['name']: c['state'] for c in docker_service.list_summaries()}
    except Exception:
        return {}


def _status(entry: dict, states: dict) -> str:
    name = entry.get('container')
    state = states.get(name)
    if state is None:
        return 'not_deployed'
    return 'running' if state == 'running' else 'stopped'


def _view(entry: dict, states: dict) -> dict:
    return {
        'id': entry.get('id'),
        'name': entry.get('name'),
        'container': entry.get('container'),
        'description': entry.get('description', ''),
        'fields': entry.get('fields', []),
        'status': _status(entry, states),
        'config': _read_config(entry),
    }


router = APIRouter(prefix='/api/pipelines', tags=['pipelines'], dependencies=[Depends(auth.require)])


@router.get('')
def list_pipelines() -> dict:
    states = _container_states()
    return {'pipelines': [_view(p, states) for p in _registry()]}


@router.get('/{pid}')
def get_pipeline(pid: str) -> dict:
    return _view(_entry(pid), _container_states())


@router.put('/{pid}/config')
def update_config(pid: str, body: ConfigBody) -> dict:
    entry = _entry(pid)
    path = _config_path(entry)
    merged = _read_config(entry)
    merged.update(body.config)  # preserve keys outside the form

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            yaml.safe_dump(merged, f, sort_keys=False, default_flow_style=False)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    log.info('pipeline %s config updated', pid)
    return _view(entry, _container_states())


@router.post('/{pid}/{action}')
def pipeline_action(pid: str, action: str) -> dict:
    if action not in ACTIONS:
        raise HTTPException(400, detail=f'unsupported action: {action}')
    entry = _entry(pid)
    container = docker_service.get(entry['container'])  # 404 if not created yet
    try:
        getattr(container, action)()
    except Exception as exc:
        raise HTTPException(502, detail=f'{action} failed: {exc}')
    log.info('pipeline %s %s', pid, action)
    return _view(entry, _container_states())
