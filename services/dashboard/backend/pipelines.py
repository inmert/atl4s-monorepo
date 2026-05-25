"""Pipeline registry — declarative description of perception / fusion
services the dashboard knows how to surface, configure, and lifecycle.

Two YAML surfaces:
- ``config/pipelines.yaml`` — the registry. Read once at startup.
- ``config/pipelines/{id}.yaml`` — per-pipeline runtime config. Read on
  every request and written by the user via PUT /api/pipelines/{id}/config.
  Each perception service is expected to mount the same file and read it
  at startup.

Container lifecycle (start/stop) goes through the docker socket the
dashboard already mounts for the Health page.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import docker
import yaml
from fastapi import APIRouter, Body, Depends, HTTPException

from backend import auth
from backend.containers import inspector

log = logging.getLogger('dashboard.pipelines')

REGISTRY_PATH = Path(os.environ.get('PIPELINES_REGISTRY', '/app/config/pipelines.yaml'))
CONFIGS_DIR = Path(os.environ.get('PIPELINES_CONFIG_DIR', '/app/config/pipelines'))

ALLOWED_FIELD_TYPES = {'string', 'number', 'slider', 'boolean', 'select', 'list_string'}


@dataclass
class Field:
    name: str
    label: str
    type: str
    default: Any = None
    options: Optional[list] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None

    def to_dict(self) -> dict:
        out = {'name': self.name, 'label': self.label, 'type': self.type, 'default': self.default}
        if self.options is not None:
            out['options'] = self.options
        if self.min is not None:
            out['min'] = self.min
        if self.max is not None:
            out['max'] = self.max
        if self.step is not None:
            out['step'] = self.step
        return out


@dataclass
class Pipeline:
    id: str
    name: str
    description: str
    kind: str
    icon: str
    container: str
    input_topics: list[str] = field(default_factory=list)
    output_topics: list[str] = field(default_factory=list)
    config_schema: list[Field] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'kind': self.kind,
            'icon': self.icon,
            'container': self.container,
            'input_topics': list(self.input_topics),
            'output_topics': list(self.output_topics),
            'config_schema': [f.to_dict() for f in self.config_schema],
        }


def _validate_field(entry: dict, pipeline_id: str, index: int) -> Field:
    for required in ('name', 'label', 'type'):
        if required not in entry:
            raise ValueError(
                f'pipelines.yaml {pipeline_id} field #{index}: missing "{required}"'
            )
    if entry['type'] not in ALLOWED_FIELD_TYPES:
        raise ValueError(
            f'pipelines.yaml {pipeline_id} field "{entry["name"]}": '
            f'unknown type "{entry["type"]}"'
        )
    if entry['type'] == 'select' and not entry.get('options'):
        raise ValueError(
            f'pipelines.yaml {pipeline_id} field "{entry["name"]}": select needs options'
        )
    return Field(
        name=str(entry['name']),
        label=str(entry['label']),
        type=str(entry['type']),
        default=entry.get('default'),
        options=entry.get('options'),
        min=entry.get('min'),
        max=entry.get('max'),
        step=entry.get('step'),
    )


def _validate_pipeline(entry: dict, index: int) -> Pipeline:
    for required in ('id', 'name', 'kind', 'icon', 'container'):
        if required not in entry:
            raise ValueError(f'pipelines.yaml entry #{index}: missing "{required}"')
    pid = str(entry['id'])
    schema = [
        _validate_field(f, pid, i)
        for i, f in enumerate(entry.get('config_schema') or [])
    ]
    return Pipeline(
        id=pid,
        name=str(entry['name']),
        description=str(entry.get('description', '')),
        kind=str(entry['kind']),
        icon=str(entry['icon']),
        container=str(entry['container']),
        input_topics=[str(x) for x in entry.get('input_topics') or []],
        output_topics=[str(x) for x in entry.get('output_topics') or []],
        config_schema=schema,
    )


def load_registry(path: Path = REGISTRY_PATH) -> list[Pipeline]:
    if not path.is_file():
        log.warning('pipelines registry not found at %s; using empty list', path)
        return []
    with path.open() as f:
        raw = yaml.safe_load(f) or []
    if not isinstance(raw, list):
        raise ValueError(f'{path}: expected a YAML list of pipelines')
    pipelines = [_validate_pipeline(entry, i) for i, entry in enumerate(raw)]
    log.info(
        'loaded %d pipelines: %s',
        len(pipelines),
        ', '.join(p.id for p in pipelines) or '(none)',
    )
    return pipelines


class Registry:
    def __init__(self) -> None:
        self._pipelines: list[Pipeline] = []

    def load(self) -> list[Pipeline]:
        CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
        self._pipelines = load_registry()
        return self._pipelines

    @property
    def pipelines(self) -> list[Pipeline]:
        return list(self._pipelines)

    def get(self, pipeline_id: str) -> Optional[Pipeline]:
        for p in self._pipelines:
            if p.id == pipeline_id:
                return p
        return None


registry = Registry()


def _config_path(pipeline_id: str) -> Path:
    return CONFIGS_DIR / f'{pipeline_id}.yaml'


def read_config(pipeline: Pipeline) -> dict:
    """Return the on-disk config merged over the schema defaults — so a partial
    file still produces a complete dict, and a missing file produces the
    default values."""
    out = {f.name: f.default for f in pipeline.config_schema}
    path = _config_path(pipeline.id)
    if path.is_file():
        try:
            with path.open() as f:
                stored = yaml.safe_load(f) or {}
            if isinstance(stored, dict):
                out.update(stored)
        except Exception:
            log.exception('failed to read %s; falling back to defaults', path)
    return out


def _coerce(value: Any, field_: Field) -> Any:
    """Lightweight server-side type coercion / validation."""
    if value is None:
        return field_.default
    t = field_.type
    if t == 'boolean':
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    if t in ('number', 'slider'):
        try:
            n = float(value)
        except (TypeError, ValueError):
            raise ValueError(f'field {field_.name}: expected a number')
        if field_.min is not None and n < field_.min:
            raise ValueError(f'field {field_.name}: {n} < min {field_.min}')
        if field_.max is not None and n > field_.max:
            raise ValueError(f'field {field_.name}: {n} > max {field_.max}')
        return n
    if t == 'select':
        s = str(value)
        if field_.options and s not in [str(o) for o in field_.options]:
            raise ValueError(
                f'field {field_.name}: "{s}" not in options {field_.options}'
            )
        return s
    if t == 'list_string':
        if isinstance(value, str):
            return [v.strip() for v in value.replace(',', ' ').split() if v.strip()]
        if isinstance(value, list):
            return [str(v) for v in value]
        raise ValueError(f'field {field_.name}: expected list or string')
    # string / fallthrough
    return str(value)


def write_config(pipeline: Pipeline, values: dict) -> dict:
    """Validate `values` against the schema and persist the merged result.
    Returns the dict that was written."""
    out: dict = {}
    for f in pipeline.config_schema:
        out[f.name] = _coerce(values.get(f.name, f.default), f)
    path = _config_path(pipeline.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.yaml.tmp')
    with tmp.open('w') as fh:
        yaml.safe_dump(out, fh, sort_keys=False, default_flow_style=False)
    tmp.replace(path)  # atomic on POSIX
    log.info('wrote %s', path)
    return out


def container_status(pipeline: Pipeline) -> dict:
    """Resolve runtime state from the docker daemon. Returns a small dict
    safe to ship to the client; never raises."""
    if not inspector.available:
        return {'state': 'unknown', 'level': 'idle', 'message': 'docker socket unavailable'}
    client = inspector._client  # already-connected DockerClient
    try:
        c = client.containers.get(pipeline.container)
    except docker.errors.NotFound:
        return {'state': 'absent', 'level': 'idle', 'message': 'container not deployed'}
    except Exception as exc:
        return {'state': 'error', 'level': 'err', 'message': str(exc)}
    state = c.attrs.get('State', {}).get('Status', 'unknown')
    level = (
        'ok' if state == 'running'
        else 'warn' if state in ('restarting', 'paused', 'created', 'removing')
        else 'err' if state in ('exited', 'dead')
        else 'idle'
    )
    return {'state': state, 'level': level, 'message': c.status}


def _container_action(pipeline: Pipeline, action: str) -> dict:
    if not inspector.available:
        raise HTTPException(status_code=503, detail='docker socket unavailable')
    client = inspector._client
    try:
        c = client.containers.get(pipeline.container)
    except docker.errors.NotFound:
        raise HTTPException(
            status_code=404,
            detail=f'container "{pipeline.container}" is not deployed (build + run the service first)',
        )
    try:
        getattr(c, action)()
    except docker.errors.APIError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return container_status(pipeline)


router = APIRouter(prefix='/api/pipelines', tags=['pipelines'])


@router.get('', dependencies=[Depends(auth.require)])
def list_pipelines() -> list[dict]:
    return [
        {**p.to_dict(), 'status': container_status(p)}
        for p in registry.pipelines
    ]


@router.get('/{pipeline_id}', dependencies=[Depends(auth.require)])
def get_pipeline(pipeline_id: str) -> dict:
    p = registry.get(pipeline_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f'unknown pipeline "{pipeline_id}"')
    return {
        **p.to_dict(),
        'status': container_status(p),
        'config': read_config(p),
    }


@router.put('/{pipeline_id}/config', dependencies=[Depends(auth.require)])
def put_config(pipeline_id: str, body: dict = Body(...)) -> dict:
    p = registry.get(pipeline_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f'unknown pipeline "{pipeline_id}"')
    try:
        written = write_config(p, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f'failed to write config: {exc}')
    return {'config': written}


@router.post('/{pipeline_id}/start', dependencies=[Depends(auth.require)])
def start_pipeline(pipeline_id: str) -> dict:
    p = registry.get(pipeline_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f'unknown pipeline "{pipeline_id}"')
    return _container_action(p, 'start')


@router.post('/{pipeline_id}/stop', dependencies=[Depends(auth.require)])
def stop_pipeline(pipeline_id: str) -> dict:
    p = registry.get(pipeline_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f'unknown pipeline "{pipeline_id}"')
    return _container_action(p, 'stop')


@router.post('/{pipeline_id}/restart', dependencies=[Depends(auth.require)])
def restart_pipeline(pipeline_id: str) -> dict:
    p = registry.get(pipeline_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f'unknown pipeline "{pipeline_id}"')
    return _container_action(p, 'restart')
