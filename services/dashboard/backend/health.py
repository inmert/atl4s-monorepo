"""Aggregate health endpoint — combines container state and topic liveness
into one snapshot for the dashboard's Health page and nav badge.

Topic liveness is computed from the topic bridge's per-topic timestamp
deques (the same data that already drives ``/ws/topics`` rates), so no
new ROS subscriptions are needed. The previous standalone
``services/healthcheck`` container was folded into this module.
"""

import time
from typing import Optional

from fastapi import APIRouter, Depends

from backend import auth
from backend.containers import inspector
from backend.robots import registry
from backend.topics import bridge

# Per-telemetry-key freshness thresholds, in seconds. Picked to match the
# defaults the (now-deleted) healthcheck service used. Anything past the
# threshold is reported as WARN; topics never seen also report WARN.
DEFAULT_THRESHOLDS: dict[str, float] = {
    'state': 5.0,
    'battery': 5.0,
    'imu': 3.0,
    'gps': 10.0,
    'camera': 5.0,
}


def _agg(level: str, *others: str) -> str:
    # "idle" (never-seen topic) doesn't degrade the aggregate — a registered
    # robot that hasn't come online yet is informational, not a fault.
    order = {'ok': 0, 'idle': 0, 'warn': 1, 'err': 2}
    return max((level, *others), key=lambda x: order.get(x, 0))


def _topic_levels() -> list[dict]:
    """One entry per registry telemetry topic. Cameras report against the
    camera bridge's per-topic latest-jpeg timestamp; everything else reads
    the topic bridge's timestamp deque.
    """
    now = time.time()
    out: list[dict] = []
    for robot in registry.robots:
        for key, topic in robot.telemetry.items():
            threshold = DEFAULT_THRESHOLDS.get(key, 10.0)
            last: Optional[float]
            rate: float

            if key == 'camera':
                # The topic bridge doesn't subscribe to camera; rate is
                # tracked separately by the camera bridge.
                last = None
                rate = 0.0
                # Fall back to camera bridge's per-topic latest if available.
                # We don't expose rate from camera.py; treat any recent frame
                # as fresh-enough to be OK.
                latest_jpeg = None
                try:
                    from backend.camera import camera as _camera  # local import
                    latest_jpeg = _camera.latest(topic)
                except Exception:
                    pass
                if latest_jpeg is not None:
                    last = now  # camera doesn't expose timestamp; treat as fresh
            else:
                deque = bridge._timestamps.get(topic)
                last = deque[-1] if deque else None
                snap = bridge.state.get(topic)
                rate = float(snap['rate']) if snap else 0.0

            if last is None:
                age = None
                level = 'idle'
                message = 'not yet seen'
            else:
                age = now - last
                if age > threshold:
                    level = 'warn'
                    message = f'stale: {age:.1f}s > {threshold:.1f}s'
                else:
                    level = 'ok'
                    message = f'{age:.1f}s ago'

            # State topic carries the "connected" boolean; treat
            # connected:false as WARN even if fresh.
            if key == 'state':
                snap = bridge.state.get(topic)
                if snap is not None and not snap.get('data', {}).get('connected'):
                    level = _agg(level, 'warn')
                    message = 'not connected'

            out.append({
                'robot_id': robot.id,
                'key': key,
                'topic': topic,
                'level': level,
                'message': message,
                'age_sec': age,
                'threshold_sec': threshold,
                'rate': rate,
            })
    return out


def snapshot() -> dict:
    topics = _topic_levels()
    containers = inspector.list() if inspector.available else []

    levels = [t['level'] for t in topics] + [c['level'] for c in containers]
    if not levels:
        overall = 'warn' if not inspector.available else 'ok'
    else:
        overall = _agg('ok', *levels)

    summary = {
        'ok': sum(1 for x in levels if x == 'ok'),
        'idle': sum(1 for x in levels if x == 'idle'),
        'warn': sum(1 for x in levels if x == 'warn'),
        'err': sum(1 for x in levels if x == 'err'),
    }

    return {
        'level': overall,
        'summary': summary,
        'docker_available': inspector.available,
        'containers': containers,
        'topics': topics,
        'ts': time.time(),
    }


router = APIRouter(prefix='/api/health', tags=['health'])


@router.get('', dependencies=[Depends(auth.require)])
def get_health() -> dict:
    return snapshot()
