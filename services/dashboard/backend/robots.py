"""Robot registry — reads ``config/robots.yaml`` once at startup and exposes
the list to the rest of the dashboard.

Adding a new robot to the YAML is enough for:
- it to appear under ``/api/robots`` (and therefore in the UI),
- the topic bridge to subscribe to every topic in its telemetry mapping,
- the camera bridge to subscribe to its camera topic (if any).
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException

from backend import auth

log = logging.getLogger('dashboard.robots')

CONFIG_PATH = Path(os.environ.get('ROBOTS_CONFIG', '/app/config/robots.yaml'))


@dataclass
class Robot:
    id: str
    name: str
    kind: str
    icon: str
    telemetry: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'kind': self.kind,
            'icon': self.icon,
            'telemetry': dict(self.telemetry),
        }


def _validate(entry: dict, index: int) -> Robot:
    for required in ('id', 'name', 'kind', 'icon'):
        if required not in entry:
            raise ValueError(f'robots.yaml entry #{index}: missing "{required}"')
    telemetry = entry.get('telemetry', {}) or {}
    if not isinstance(telemetry, dict):
        raise ValueError(f'robots.yaml entry "{entry["id"]}": telemetry must be a mapping')
    return Robot(
        id=str(entry['id']),
        name=str(entry['name']),
        kind=str(entry['kind']),
        icon=str(entry['icon']),
        telemetry={k: str(v) for k, v in telemetry.items() if v},
    )


def load_robots(path: Path = CONFIG_PATH) -> list[Robot]:
    if not path.is_file():
        log.warning('robots config not found at %s; using empty registry', path)
        return []
    with path.open() as f:
        raw = yaml.safe_load(f) or []
    if not isinstance(raw, list):
        raise ValueError(f'{path}: expected a YAML list of robots')
    robots = [_validate(entry, i) for i, entry in enumerate(raw)]
    logger_msg = ', '.join(f'{r.id} ({r.kind})' for r in robots) or '(none)'
    log.info('loaded %d robots: %s', len(robots), logger_msg)
    return robots


def topics_in_registry(robots: list[Robot]) -> set[str]:
    """Union of every telemetry topic referenced across the registry.

    Used by the topic bridge to know what to subscribe to.
    """
    seen: set[str] = set()
    for r in robots:
        for topic in r.telemetry.values():
            seen.add(topic)
    return seen


def camera_topics(robots: list[Robot]) -> dict[str, str]:
    """Robot id → camera topic, for robots that have a camera configured."""
    return {r.id: r.telemetry['camera'] for r in robots if 'camera' in r.telemetry}


class Registry:
    """In-process holder. Populated at startup, read by routes + bridges."""

    def __init__(self) -> None:
        self._robots: list[Robot] = []

    def load(self) -> list[Robot]:
        self._robots = load_robots()
        return self._robots

    @property
    def robots(self) -> list[Robot]:
        return list(self._robots)

    def get(self, robot_id: str) -> Optional[Robot]:
        for r in self._robots:
            if r.id == robot_id:
                return r
        return None


registry = Registry()


router = APIRouter(prefix='/api/robots', tags=['robots'])


@router.get('', dependencies=[Depends(auth.require)])
def list_robots() -> list[dict]:
    return [r.to_dict() for r in registry.robots]


@router.get('/{robot_id}', dependencies=[Depends(auth.require)])
def get_robot(robot_id: str) -> dict:
    r = registry.get(robot_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f'unknown robot "{robot_id}"')
    return r.to_dict()
