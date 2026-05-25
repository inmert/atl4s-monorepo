#!/usr/bin/env python3
"""Publish synthetic LaserScan frames on /lidar/scan at ~5 Hz.

A 360°, 720-ray scan with two solid returns:
- a tank-shaped footprint (~6 m × 3.5 m) at one bearing
- an aircraft-shaped footprint (~16 m × 14 m) at another bearing
- a sprinkle of long-range noise so DBSCAN has reason to ignore stuff

Mirror of publish_fake_lidar.py for the 2D-input branch of the
detector — drives perception-lidar end-to-end when the configured
``input_type`` is ``laserscan``.
"""

from __future__ import annotations

import math

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Header

RATE_HZ = 5.0
NUM_RAYS = 720          # 0.5° resolution over a full 360°
RANGE_MIN = 0.1         # m
RANGE_MAX = 80.0        # m


def _ray_hits_box(angle: float, cx: float, cy: float, sx: float, sy: float) -> float:
    """Return the distance from the origin to the first intersection of a
    ray at ``angle`` (radians) with the axis-aligned box centred at
    (cx, cy) with extents (sx, sy). Returns ``inf`` if no intersection."""
    dx, dy = math.cos(angle), math.sin(angle)
    hx, hy = sx / 2, sy / 2
    t_near = -math.inf
    t_far = math.inf
    # Slab intersection on x
    if dx == 0:
        if cx - hx > 0 or cx + hx < 0:
            return math.inf
    else:
        t1 = (cx - hx) / dx
        t2 = (cx + hx) / dx
        t_near = max(t_near, min(t1, t2))
        t_far = min(t_far, max(t1, t2))
    # Slab intersection on y
    if dy == 0:
        if cy - hy > 0 or cy + hy < 0:
            return math.inf
    else:
        t1 = (cy - hy) / dy
        t2 = (cy + hy) / dy
        t_near = max(t_near, min(t1, t2))
        t_far = min(t_far, max(t1, t2))
    if t_near > t_far or t_far < 0:
        return math.inf
    return t_near if t_near >= 0 else t_far


def _synthetic_ranges(angles: np.ndarray) -> np.ndarray:
    """Render a 360° scan with a tank and an aircraft footprint."""
    tank = (15.0, -8.0, 6.5, 3.5)        # cx, cy, sx, sy (metres)
    aircraft = (40.0, 5.0, 16.0, 14.0)
    ranges = np.full(angles.shape, math.inf, dtype=np.float32)
    for a in (tank, aircraft):
        for i, theta in enumerate(angles):
            d = _ray_hits_box(theta, *a)
            if d < ranges[i]:
                ranges[i] = d
    # Replace inf with a slightly noisy "no return" (just below max range).
    no_return = ~np.isfinite(ranges)
    ranges[no_return] = RANGE_MAX - np.random.uniform(0.0, 0.2, size=int(no_return.sum()))
    return ranges


class FakeScan(Node):
    def __init__(self) -> None:
        super().__init__('fake_scan_publisher')
        qos = QoSProfile(depth=2, reliability=QoSReliabilityPolicy.BEST_EFFORT)
        self.pub = self.create_publisher(LaserScan, '/lidar/scan', qos)
        self.timer = self.create_timer(1.0 / RATE_HZ, self._tick)
        # Pre-compute angle array — same every tick.
        self.angle_min = -math.pi
        self.angle_max = math.pi
        self.angle_increment = (self.angle_max - self.angle_min) / NUM_RAYS
        self.angles = (
            self.angle_min + np.arange(NUM_RAYS, dtype=np.float32) * self.angle_increment
        )
        self.get_logger().info(
            f'publishing /lidar/scan at {RATE_HZ} Hz '
            f'({NUM_RAYS} rays over 360°, tank+aircraft footprints)'
        )

    def _tick(self) -> None:
        ranges = _synthetic_ranges(self.angles)
        stamp = self.get_clock().now().to_msg()
        msg = LaserScan(
            header=Header(stamp=stamp, frame_id='lidar'),
            angle_min=self.angle_min,
            angle_max=self.angle_max,
            angle_increment=self.angle_increment,
            time_increment=0.0,
            scan_time=1.0 / RATE_HZ,
            range_min=RANGE_MIN,
            range_max=RANGE_MAX,
            ranges=ranges.tolist(),
            intensities=[],
        )
        self.pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = FakeScan()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
