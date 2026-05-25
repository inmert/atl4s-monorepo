#!/usr/bin/env python3
"""perception-lidar — subscribes to a PointCloud2 input and publishes
``atl4s_msgs/LidarDetectionArray`` of clustered objects.

The detector is a classical scaffold: DBSCAN cluster the (above-ground,
within-range) points, compute each cluster's axis-aligned bounding box,
and score it against per-class shape priors (aircraft = elongated +
relatively flat, tank = compact + cubic-ish). It logs at startup that
the config-selected ``model_variant`` (pointpillars / centerpoint /
voxelnet) is currently a no-op and that classical clustering is in
effect — the path to a real learned model is to replace ``_classify``
and ``_score`` in this file.

Runtime config is read once at startup from the YAML file at
``LIDAR_CONFIG`` (default ``/app/config/pipelines/perception-lidar.yaml``),
which the dashboard writes when the user clicks Save in the Pipelines
form. Restart the container to pick up changes.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import rclpy
import yaml
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from sklearn.cluster import DBSCAN
from std_msgs.msg import Header
from geometry_msgs.msg import Point, Vector3

from atl4s_msgs.msg import LidarDetection, LidarDetectionArray


# Ground / range filtering. Conservative defaults; not exposed in the
# schema yet because the user has no real lidar to tune against. Move
# into config/pipelines/perception-lidar.yaml when there's a need.
GROUND_Z_THRESHOLD = -1.0
MAX_RANGE_M = 80.0
MIN_CLUSTER_POINTS = 12
DBSCAN_EPS = 0.6        # metres
DBSCAN_MIN_SAMPLES = 8

# Class shape priors. Used by both _classify (best-fit label) and _score
# (heuristic confidence). Add new classes by extending PROTOTYPES and the
# allow-list will inherit them automatically.
@dataclass(frozen=True)
class ShapePrior:
    length: tuple[float, float]  # (min, max) metres
    width: tuple[float, float]
    height: tuple[float, float]
    length_over_width: tuple[float, float]


PROTOTYPES: dict[str, ShapePrior] = {
    'aircraft': ShapePrior(
        length=(8.0, 50.0),
        width=(6.0, 50.0),
        height=(1.5, 8.0),
        length_over_width=(0.8, 1.6),  # roughly square footprint (wingspan ~ length)
    ),
    'tank': ShapePrior(
        length=(5.0, 12.0),
        width=(2.5, 5.0),
        height=(1.5, 3.5),
        length_over_width=(1.5, 4.0),  # elongated
    ),
}


# ─── Config ────────────────────────────────────────────────────────────

CONFIG_PATH = Path(os.environ.get('LIDAR_CONFIG', '/app/config/pipelines/perception-lidar.yaml'))


@dataclass
class Config:
    model_variant: str
    confidence_threshold: float
    target_classes: list[str]
    input_topic: str
    output_topic: str
    enable_tracking: bool


CONFIG_DEFAULTS = Config(
    model_variant='pointpillars',
    confidence_threshold=0.5,
    target_classes=['aircraft', 'tank'],
    input_topic='/lidar/points',
    output_topic='/perception/lidar/detections',
    enable_tracking=False,
)


def load_config(path: Path = CONFIG_PATH, log: Optional[logging.Logger] = None) -> Config:
    if not path.is_file():
        if log:
            log.warning('config not found at %s; using defaults', path)
        return CONFIG_DEFAULTS
    with path.open() as f:
        raw = yaml.safe_load(f) or {}
    cls = list(raw.get('target_classes') or CONFIG_DEFAULTS.target_classes)
    return Config(
        model_variant=str(raw.get('model_variant', CONFIG_DEFAULTS.model_variant)),
        confidence_threshold=float(raw.get('confidence_threshold', CONFIG_DEFAULTS.confidence_threshold)),
        target_classes=[str(c) for c in cls],
        input_topic=str(raw.get('input_topic', CONFIG_DEFAULTS.input_topic)),
        output_topic=str(raw.get('output_topic', CONFIG_DEFAULTS.output_topic)),
        enable_tracking=bool(raw.get('enable_tracking', CONFIG_DEFAULTS.enable_tracking)),
    )


# ─── Detection ─────────────────────────────────────────────────────────

def _within(value: float, bounds: tuple[float, float]) -> float:
    """1.0 if `value` is in `bounds`, otherwise a soft fall-off towards 0."""
    lo, hi = bounds
    if value < lo:
        return max(0.0, value / lo) if lo > 0 else 0.0
    if value > hi:
        return max(0.0, hi / value) if value > 0 else 0.0
    return 1.0


def _classify(bbox: ShapePrior_like, score_above: float) -> tuple[str, float]:
    """Return the best-fit class label + its score across all known prototypes.

    Returns ('other', 0.0) if no prototype matches above `score_above`.
    """
    best_label = 'other'
    best_score = 0.0
    for label, prior in PROTOTYPES.items():
        score = _score(bbox, prior)
        if score > best_score:
            best_label = label
            best_score = score
    if best_score < score_above:
        return ('other', best_score)
    return (best_label, best_score)


def _score(bbox: ShapePrior_like, prior: ShapePrior) -> float:
    """Geometric mean of per-axis fit scores. Returns 0.0..1.0."""
    if bbox.width <= 0:
        return 0.0
    parts = [
        _within(bbox.length, prior.length),
        _within(bbox.width, prior.width),
        _within(bbox.height, prior.height),
        _within(bbox.length / max(bbox.width, 0.01), prior.length_over_width),
    ]
    # Geometric mean — one bad axis dominates, mirroring "all dimensions
    # must look right" rather than "any one will do".
    prod = 1.0
    for p in parts:
        prod *= max(p, 1e-3)
    return prod ** (1.0 / len(parts))


@dataclass
class BBox:
    cx: float
    cy: float
    cz: float
    length: float
    width: float
    height: float


# Type alias used by _classify / _score; keeps the signature ergonomic
# without an extra import.
ShapePrior_like = BBox


def _bbox(points: np.ndarray) -> BBox:
    """Axis-aligned bounding box of `points` (N×3 array of x,y,z)."""
    lo = points.min(axis=0)
    hi = points.max(axis=0)
    extent = hi - lo
    centre = (hi + lo) * 0.5
    # length = larger horizontal extent, width = smaller, height = z extent.
    horiz_a, horiz_b = float(extent[0]), float(extent[1])
    length = max(horiz_a, horiz_b)
    width = min(horiz_a, horiz_b)
    height = float(extent[2])
    return BBox(
        cx=float(centre[0]),
        cy=float(centre[1]),
        cz=float(centre[2]),
        length=length,
        width=width,
        height=height,
    )


# ─── ROS node ──────────────────────────────────────────────────────────

def _be_qos(depth: int = 5) -> QoSProfile:
    return QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=depth,
        reliability=QoSReliabilityPolicy.BEST_EFFORT,
        durability=QoSDurabilityPolicy.VOLATILE,
    )


class LidarDetector(Node):
    def __init__(self, cfg: Config) -> None:
        super().__init__('perception_lidar')
        self.cfg = cfg
        self._track_counter = 0

        self.get_logger().info(
            f'config: model_variant={cfg.model_variant}, '
            f'confidence>={cfg.confidence_threshold}, '
            f'targets={cfg.target_classes}, '
            f'tracking={"on" if cfg.enable_tracking else "off"}'
        )
        if cfg.model_variant in ('pointpillars', 'centerpoint', 'voxelnet'):
            self.get_logger().warn(
                f'model_variant={cfg.model_variant} selected, but using '
                'classical clustering until a learned model is wired '
                '(replace _classify/_score in lidar_detector.py)'
            )
        if cfg.enable_tracking:
            self.get_logger().warn('enable_tracking=true requested, but tracking is not implemented yet; track_id will be 0')

        self.sub = self.create_subscription(
            PointCloud2, cfg.input_topic, self._on_cloud, _be_qos()
        )
        self.pub = self.create_publisher(
            LidarDetectionArray, cfg.output_topic, _be_qos()
        )
        self.get_logger().info(
            f'subscribed to {cfg.input_topic}; publishing to {cfg.output_topic}'
        )

    def _on_cloud(self, msg: PointCloud2) -> None:
        try:
            detections = self._detect(msg)
        except Exception:
            self.get_logger().exception('detection failed; dropping frame')
            return

        out = LidarDetectionArray()
        out.header = msg.header
        out.detections = detections
        self.pub.publish(out)

    def _detect(self, msg: PointCloud2) -> list[LidarDetection]:
        # read_points returns a structured numpy array; project to N×3.
        raw = point_cloud2.read_points(
            msg, field_names=('x', 'y', 'z'), skip_nans=True
        )
        # Some ROS distributions return a structured array, others a list of
        # tuples. Normalise either way.
        if hasattr(raw, 'view'):
            xyz = np.vstack([raw['x'], raw['y'], raw['z']]).T.astype(np.float32)
        else:
            xyz = np.asarray(list(raw), dtype=np.float32)
            if xyz.ndim == 1 and xyz.size:
                xyz = xyz.reshape(-1, 3)

        if xyz.size == 0:
            return []

        # Ground + range filter.
        above_ground = xyz[:, 2] > GROUND_Z_THRESHOLD
        in_range = np.linalg.norm(xyz[:, :2], axis=1) < MAX_RANGE_M
        xyz = xyz[above_ground & in_range]
        if len(xyz) < MIN_CLUSTER_POINTS:
            return []

        labels = DBSCAN(eps=DBSCAN_EPS, min_samples=DBSCAN_MIN_SAMPLES).fit(xyz).labels_
        out: list[LidarDetection] = []
        for cluster_id in np.unique(labels):
            if cluster_id == -1:  # noise
                continue
            cluster = xyz[labels == cluster_id]
            if len(cluster) < MIN_CLUSTER_POINTS:
                continue
            bbox = _bbox(cluster)
            label, score = _classify(bbox, score_above=0.05)
            if score < self.cfg.confidence_threshold:
                continue
            if self.cfg.target_classes and label not in self.cfg.target_classes:
                continue

            det = LidarDetection()
            det.header = Header()
            det.header.stamp = msg.header.stamp
            det.header.frame_id = msg.header.frame_id
            det.class_id = label
            det.score = float(score)
            det.center = Point(x=bbox.cx, y=bbox.cy, z=bbox.cz)
            det.size = Vector3(x=bbox.length, y=bbox.width, z=bbox.height)
            det.track_id = 0
            out.append(det)
        return out


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s'
    )
    log = logging.getLogger('perception-lidar')
    cfg = load_config(log=log)

    rclpy.init()
    node = LidarDetector(cfg)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
