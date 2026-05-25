"""ROS graph endpoint + on-demand sampling.

``GET /api/ros/topics`` walks the rclpy graph and reports every topic
on the bus, its type(s), publisher / subscriber counts, and a one-glyph
QoS summary per endpoint. Cheap — graph queries are cached locally by
the middleware.

``WS /ws/ros/sample/{topic}`` opens a transient Best-Effort
subscription via the topic bridge and streams parsed JSON messages
until the client disconnects.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from rclpy.qos import QoSDurabilityPolicy, QoSReliabilityPolicy

from backend import auth
from backend.topics import bridge

log = logging.getLogger('dashboard.ros')


def _reliability(qp) -> str:
    if qp.reliability == QoSReliabilityPolicy.RELIABLE:
        return 'RE'
    if qp.reliability == QoSReliabilityPolicy.BEST_EFFORT:
        return 'BE'
    return '?'


def _durability(qp) -> str:
    if qp.durability == QoSDurabilityPolicy.TRANSIENT_LOCAL:
        return 'TL'
    if qp.durability == QoSDurabilityPolicy.VOLATILE:
        return 'VOL'
    return '?'


def _endpoint_summary(info_list) -> list[dict]:
    out: list[dict] = []
    for ep in info_list or ():
        ns = ep.node_namespace if ep.node_namespace not in (None, '/') else ''
        out.append({
            'node': f'{ns}/{ep.node_name}'.replace('//', '/'),
            'qos': f'{_reliability(ep.qos_profile)}/{_durability(ep.qos_profile)}',
        })
    return out


router = APIRouter(prefix='/api/ros', tags=['ros'])


@router.get('/topics', dependencies=[Depends(auth.require)])
def list_topics() -> list[dict]:
    node = bridge.node
    if node is None:
        raise HTTPException(status_code=503, detail='topic bridge not ready')

    items: list[dict] = []
    for name, types in node.get_topic_names_and_types():
        try:
            pubs = node.get_publishers_info_by_topic(name)
        except Exception:
            pubs = []
        try:
            subs = node.get_subscriptions_info_by_topic(name)
        except Exception:
            subs = []
        # If our own bridge is the only subscriber, hide it from the
        # subscriber count so the page reflects "who else is on this topic".
        external_subs = [s for s in subs if s.node_name != 'atl4s_dashboard_topics']
        items.append({
            'name': name,
            'types': list(types),
            'pub_count': len(pubs),
            'sub_count': len(external_subs),
            'pubs': _endpoint_summary(pubs),
            'subs': _endpoint_summary(external_subs),
        })
    items.sort(key=lambda x: x['name'])
    return items


async def sample_socket(ws, topic: str) -> None:
    """WebSocket handler — opens a per-socket sampling queue and streams
    one snapshot per message until the client disconnects.

    Returns once the socket closes. Raises nothing; close codes are sent
    on the wire for client-visible errors.
    """
    if not auth.check_websocket(ws):
        await ws.close(code=4401)
        return
    if bridge.node is None:
        await ws.close(code=4503)
        return
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    if not bridge.add_sample(topic, queue):
        await ws.close(code=4404)
        return
    await ws.accept()
    try:
        # Replay the last known snapshot immediately so the inspector isn't
        # blank when the topic is low-rate (e.g. /tf_static, /clock at boot).
        last = bridge.state.get(topic)
        if last is not None:
            await ws.send_json(last)
        while True:
            msg = await queue.get()
            await ws.send_json(msg)
    finally:
        bridge.remove_sample(topic, queue)


# Re-exported for main.py to keep import order simple.
__all__ = ['router', 'sample_socket']
