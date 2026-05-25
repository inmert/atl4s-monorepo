"""ROS topic bridge — fans out a curated set of ROS topics to WebSocket clients.

Runs an rclpy executor in a daemon thread; callbacks update an in-memory
``state`` snapshot and push deltas to per-client asyncio queues via
``run_coroutine_threadsafe``. Subscribers join with Best-Effort QoS to
match the (Best-Effort) /mavros/* publishers.

The subscribed topic set is the union of:
- a small base set (``BASE_TOPICS``),
- every telemetry topic referenced by every robot in the registry
  (resolved through ``TELEMETRY_TYPES``),
- any topic under ``/perception/*`` or ``/fusion/*`` that appears on the
  bus after startup (dynamic discovery every 5 s).
"""

import asyncio
import json
import logging
import math
import threading
import time
from collections import deque
from typing import Iterable, Optional

from mavros_msgs.msg import State
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from rosidl_runtime_py import message_to_ordereddict
from rosidl_runtime_py.utilities import get_message
from sensor_msgs.msg import BatteryState, Imu, NavSatFix

log = logging.getLogger('dashboard.topics')

DISCOVERY_PREFIXES = ('/perception/', '/fusion/')
DISCOVERY_PERIOD_SEC = 5.0

_BE_QOS = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10,
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    durability=QoSDurabilityPolicy.VOLATILE,
)

# Pipeline-wide topics that aren't tied to any one robot. Currently empty —
# /atl4s/health was retired when the standalone healthcheck service was
# folded into the dashboard (topic-liveness is now computed from the
# bridge's own `_timestamps` and surfaced via /api/health).
BASE_TOPICS: list[tuple[str, type]] = []

# Maps a telemetry-mapping key (from robots.yaml) to the ROS message class.
# Camera frames are handled separately by the camera bridge.
TELEMETRY_TYPES: dict[str, type] = {
    'state': State,
    'battery': BatteryState,
    'imu': Imu,
    'gps': NavSatFix,
}


def topics_from_registry(robots: Iterable) -> list[tuple[str, type]]:
    """Resolve every (topic, msg_type) referenced by the registry's telemetry
    mappings. Unknown keys are skipped with a warning."""
    out: list[tuple[str, type]] = []
    for r in robots:
        for key, topic in r.telemetry.items():
            if key == 'camera':
                continue  # handled by camera bridge
            msg_type = TELEMETRY_TYPES.get(key)
            if msg_type is None:
                log.warning('skipping unknown telemetry key "%s" for %s', key, r.id)
                continue
            out.append((topic, msg_type))
    return out


def _sanitize_for_json(obj):
    """Walk a Python native and replace NaN/Inf floats with None.

    ROS messages frequently carry NaN in optional fields the source can't
    measure (e.g. ArduPilot reports `charge`/`capacity`/`design_capacity`
    on `sensor_msgs/BatteryState` as NaN). Python's default `json.dumps`
    emits these as the literal token `NaN`, which is not valid JSON
    (RFC 8259) — the browser's `JSON.parse` rejects the whole frame and
    every consumer of that topic sees no data. Convert to `null` so the
    frontend can treat the field as absent and fall through to its
    "—" placeholder.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def _to_json_safe(msg) -> dict:
    # `default=str` is the catch-all for ROS types json doesn't know how to
    # serialize directly (mostly OrderedDict cells, bytes via byte-field
    # gotcha). The pre-sanitize pass replaces NaN/Inf with None before
    # json.dumps so the eventual websocket frame stays valid JSON.
    return json.loads(
        json.dumps(_sanitize_for_json(message_to_ordereddict(msg)), default=str)
    )


class TopicBridge:
    def __init__(self) -> None:
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.state: dict[str, dict] = {}
        self._timestamps: dict[str, deque] = {}
        self._subscribers: set[asyncio.Queue] = set()
        self._discovered: set[str] = set()
        # Per-topic queues for the ROS page's "inspect" sampler. Independent
        # of the broadcast `_subscribers` set; only frames for the matching
        # topic are routed here.
        self._sample_queues: dict[str, set[asyncio.Queue]] = {}
        self._extra_topics: list[tuple[str, type]] = []
        self._node: Optional[Node] = None
        self._executor: Optional[SingleThreadedExecutor] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def node(self) -> Optional[Node]:
        return self._node

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def set_extra_topics(self, topics: list[tuple[str, type]]) -> None:
        """Topics to subscribe in addition to BASE_TOPICS. Must be set before
        ``start()``; duplicates with BASE_TOPICS are de-duplicated by name."""
        self._extra_topics = list(topics)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name='ros-topics', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self) -> None:
        try:
            self._node = Node('atl4s_dashboard_topics')
            subscribed: set[str] = set()
            for topic, msg_type in BASE_TOPICS + self._extra_topics:
                if topic in subscribed:
                    continue
                self._subscribe(topic, msg_type)
                subscribed.add(topic)
            self._node.create_timer(DISCOVERY_PERIOD_SEC, self._discover)
            self._executor = SingleThreadedExecutor()
            self._executor.add_node(self._node)
            log.info('subscribed to %d topics; discovering %s', len(subscribed), DISCOVERY_PREFIXES)
            while self._running:
                self._executor.spin_once(timeout_sec=0.1)
        except Exception:
            log.exception('topic bridge crashed')
        finally:
            if self._node is not None:
                self._node.destroy_node()

    def _subscribe(self, topic: str, msg_type) -> None:
        assert self._node is not None
        self._node.create_subscription(
            msg_type, topic,
            lambda msg, t=topic: self._on_message(t, msg),
            _BE_QOS,
        )
        self._timestamps.setdefault(topic, deque(maxlen=20))
        self._discovered.add(topic)

    def _discover(self) -> None:
        if self._node is None:
            return
        for name, types in self._node.get_topic_names_and_types():
            if name in self._discovered:
                continue
            if not any(name.startswith(p) for p in DISCOVERY_PREFIXES):
                continue
            if not types:
                continue
            try:
                msg_class = get_message(types[0])
            except Exception:
                log.warning('cannot resolve type %s for %s; skipping', types[0], name)
                self._discovered.add(name)  # don't retry every cycle
                continue
            self._subscribe(name, msg_class)
            log.info('discovered %s (%s)', name, types[0])

    def _on_message(self, topic: str, msg) -> None:
        now = time.time()
        timestamps = self._timestamps[topic]
        timestamps.append(now)
        rate = 0.0
        if len(timestamps) >= 2:
            window = timestamps[-1] - timestamps[0]
            if window > 0:
                rate = (len(timestamps) - 1) / window
        try:
            data = _to_json_safe(msg)
        except Exception:
            log.exception('failed to serialize %s', topic)
            return
        snapshot = {'topic': topic, 'data': data, 'rate': round(rate, 2), 'ts': now}
        self.state[topic] = snapshot
        if self.loop is None:
            return
        for queue in list(self._subscribers):
            asyncio.run_coroutine_threadsafe(self._safe_put(queue, snapshot), self.loop)
        # Per-topic sample queues (ROS page inspect drawer).
        for queue in list(self._sample_queues.get(topic, ())):
            asyncio.run_coroutine_threadsafe(self._safe_put(queue, snapshot), self.loop)

    @staticmethod
    async def _safe_put(queue: asyncio.Queue, item: dict) -> None:
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            # Drop on the floor; the client is slower than the topic.
            pass

    def snapshot(self) -> list[dict]:
        return list(self.state.values())

    def add_subscriber(self, queue: asyncio.Queue) -> None:
        self._subscribers.add(queue)

    def remove_subscriber(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def add_sample(self, topic: str, queue: asyncio.Queue) -> bool:
        """Open a per-topic sampling stream for ``queue``. If the topic isn't
        already subscribed, looks up its type via the graph and creates a
        Best-Effort subscription. Returns False if the topic isn't on the
        bus or its type can't be resolved.

        The created subscription is persistent (we don't tear it down when
        the last sample client leaves) — simpler than ref-counting, and
        memory grows only on first sample per topic, not per client.
        """
        if self._node is None:
            return False
        if topic not in self._discovered:
            graph = dict(self._node.get_topic_names_and_types())
            types = graph.get(topic) or []
            if not types:
                return False
            try:
                msg_class = get_message(types[0])
            except Exception:
                log.warning('cannot resolve type %s for %s; refusing sample', types[0], topic)
                return False
            self._subscribe(topic, msg_class)
            log.info('sample-subscribed %s (%s)', topic, types[0])
        self._sample_queues.setdefault(topic, set()).add(queue)
        return True

    def remove_sample(self, topic: str, queue: asyncio.Queue) -> None:
        qs = self._sample_queues.get(topic)
        if qs:
            qs.discard(queue)
            if not qs:
                self._sample_queues.pop(topic, None)


bridge = TopicBridge()
