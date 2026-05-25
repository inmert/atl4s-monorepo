"""Camera frame bridge — re-encodes ``/camera/image`` to JPEG and fans out
to WebSocket clients as binary frames.

The dashboard backend runs this in a daemon thread alongside the topic
bridge. JPEG quality is tuned for ~50 KB per frame at 640×480, giving a
few hundred KB/s at the upstream's 5 Hz.
"""

import asyncio
import logging
import threading
from typing import Optional

import cv2
import numpy as np
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from sensor_msgs.msg import Image

log = logging.getLogger('dashboard.camera')

_BE_QOS = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=2,
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    durability=QoSDurabilityPolicy.VOLATILE,
)

_JPEG_QUALITY = 70


class CameraBridge:
    def __init__(self) -> None:
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.latest_jpeg: Optional[bytes] = None
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
        self._thread = threading.Thread(target=self._run, name='ros-camera', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self) -> None:
        try:
            self._node = Node('atl4s_dashboard_camera')
            self._node.create_subscription(Image, '/camera/image', self._on_image, _BE_QOS)
            self._executor = SingleThreadedExecutor()
            self._executor.add_node(self._node)
            log.info('subscribed to /camera/image')
            while self._running:
                self._executor.spin_once(timeout_sec=0.1)
        except Exception:
            log.exception('camera bridge crashed')
        finally:
            if self._node is not None:
                self._node.destroy_node()

    def _on_image(self, msg: Image) -> None:
        try:
            buf = np.frombuffer(msg.data, dtype=np.uint8)
            if msg.encoding == 'rgb8':
                img = buf.reshape((msg.height, msg.width, 3))
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            elif msg.encoding == 'bgr8':
                img = buf.reshape((msg.height, msg.width, 3))
            elif msg.encoding == 'mono8':
                img = buf.reshape((msg.height, msg.width))
            else:
                log.warning('unsupported encoding: %s', msg.encoding)
                return
        except Exception:
            log.exception('failed to decode image')
            return

        ok, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
        if not ok:
            return
        jpeg = encoded.tobytes()
        self.latest_jpeg = jpeg
        if self.loop is None:
            return
        for queue in list(self._subscribers):
            asyncio.run_coroutine_threadsafe(self._safe_put(queue, jpeg), self.loop)

    @staticmethod
    async def _safe_put(queue: asyncio.Queue, item: bytes) -> None:
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            pass

    def add_subscriber(self, queue: asyncio.Queue) -> None:
        self._subscribers.add(queue)

    def remove_subscriber(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)


camera = CameraBridge()
