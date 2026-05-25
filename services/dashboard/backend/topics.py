"""ROS topic bridge — fans out a curated set of ROS topics to WebSocket clients.

Runs an rclpy executor in a daemon thread; callbacks update an in-memory
``state`` snapshot and push deltas to per-client asyncio queues via
``run_coroutine_threadsafe``. Subscribers join with Best-Effort QoS to
match the (Best-Effort) /mavros/* publishers.
"""

import asyncio
import json
import logging
import threading
import time
from collections import deque
from typing import Optional

from diagnostic_msgs.msg import DiagnosticArray
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
from sensor_msgs.msg import BatteryState, Imu, NavSatFix

log = logging.getLogger('dashboard.topics')

_BE_QOS = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10,
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    durability=QoSDurabilityPolicy.VOLATILE,
)

# Curated set. Camera image is on a separate /ws/camera (see backend.camera).
TOPICS = [
    ('/mavros/state', State),
    ('/mavros/battery', BatteryState),
    ('/mavros/imu/data', Imu),
    ('/mavros/global_position/global', NavSatFix),
    ('/atl4s/health', DiagnosticArray),
]


def _to_json_safe(msg) -> dict:
    return json.loads(json.dumps(message_to_ordereddict(msg), default=str))


class TopicBridge:
    def __init__(self) -> None:
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.state: dict[str, dict] = {}
        self._timestamps: dict[str, deque] = {}
        self._subscribers: set[asyncio.Queue] = set()
        self._node: Optional[Node] = None
        self._executor: Optional[SingleThreadedExecutor] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

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
            for topic, msg_type in TOPICS:
                self._node.create_subscription(
                    msg_type, topic,
                    lambda msg, t=topic: self._on_message(t, msg),
                    _BE_QOS,
                )
                self._timestamps[topic] = deque(maxlen=20)
            self._executor = SingleThreadedExecutor()
            self._executor.add_node(self._node)
            log.info('subscribed to %d topics', len(TOPICS))
            while self._running:
                self._executor.spin_once(timeout_sec=0.1)
        except Exception:
            log.exception('topic bridge crashed')
        finally:
            if self._node is not None:
                self._node.destroy_node()

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


bridge = TopicBridge()
