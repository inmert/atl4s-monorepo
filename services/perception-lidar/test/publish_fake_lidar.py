#!/usr/bin/env python3
"""Publish synthetic PointCloud2 frames on /lidar/points at ~5 Hz.

Each frame contains:
- a tank-shaped cluster (~6 m × 3.5 m × 2.4 m) at a fixed offset
- an aircraft-shaped cluster (~16 m × 14 m × 3.5 m) at another offset
- a sprinkle of uniform noise across the workspace

Used to verify perception-lidar end-to-end on a host that has no real
lidar source (see ../README.md "Testing without real lidar").
"""

from __future__ import annotations

import struct

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header

RATE_HZ = 5.0


def _cluster(center: tuple[float, float, float], size: tuple[float, float, float], n: int) -> np.ndarray:
    """N random points inside an axis-aligned box of `size` centred at `center`."""
    cx, cy, cz = center
    sx, sy, sz = size
    xs = np.random.uniform(cx - sx / 2, cx + sx / 2, n)
    ys = np.random.uniform(cy - sy / 2, cy + sy / 2, n)
    zs = np.random.uniform(cz - sz / 2, cz + sz / 2, n)
    return np.column_stack([xs, ys, zs]).astype(np.float32)


def _synthetic_frame() -> np.ndarray:
    tank = _cluster(center=(15.0, -8.0, 1.2), size=(6.5, 3.5, 2.4), n=300)
    aircraft = _cluster(center=(40.0, 5.0, 1.8), size=(16.0, 14.0, 3.5), n=600)
    noise = np.column_stack([
        np.random.uniform(-30.0, 60.0, 80),
        np.random.uniform(-30.0, 30.0, 80),
        np.random.uniform(-0.9, 6.0, 80),
    ]).astype(np.float32)
    return np.vstack([tank, aircraft, noise])


def _pack(points: np.ndarray, stamp, frame_id: str) -> PointCloud2:
    header = Header(stamp=stamp, frame_id=frame_id)
    msg = PointCloud2()
    msg.header = header
    msg.height = 1
    msg.width = points.shape[0]
    msg.is_dense = True
    msg.is_bigendian = False
    msg.point_step = 12  # 3 × float32
    msg.row_step = msg.point_step * msg.width
    msg.fields = [
        PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
    ]
    buf = bytearray()
    for x, y, z in points:
        buf.extend(struct.pack('fff', float(x), float(y), float(z)))
    msg.data = bytes(buf)
    return msg


class FakeLidar(Node):
    def __init__(self) -> None:
        super().__init__('fake_lidar_publisher')
        qos = QoSProfile(depth=2, reliability=QoSReliabilityPolicy.BEST_EFFORT)
        self.pub = self.create_publisher(PointCloud2, '/lidar/points', qos)
        self.timer = self.create_timer(1.0 / RATE_HZ, self._tick)
        self.get_logger().info(
            f'publishing /lidar/points at {RATE_HZ} Hz '
            '(1 tank-shaped cluster, 1 aircraft-shaped cluster, ~80 noise points)'
        )

    def _tick(self) -> None:
        pts = _synthetic_frame()
        msg = _pack(pts, stamp=self.get_clock().now().to_msg(), frame_id='lidar')
        self.pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = FakeLidar()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
