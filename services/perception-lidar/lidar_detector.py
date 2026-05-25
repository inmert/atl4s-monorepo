#!/usr/bin/env python3
"""perception-lidar — subscribes to a lidar input topic (PointCloud2 for
3D lidars, LaserScan for planar 2D lidars) and publishes
``atl4s_msgs/LidarDetectionArray`` of clustered objects plus
``visualization_msgs/MarkerArray`` so Foxglove Studio's 3D panel can
render the boxes directly.

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
from sensor_msgs.msg import LaserScan, PointCloud2
from sensor_msgs_py import point_cloud2
from sklearn.cluster import DBSCAN
from std_msgs.msg import ColorRGBA, Header
from geometry_msgs.msg import Point, Vector3
from visualization_msgs.msg import Marker, MarkerArray

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

# Marker palette for Foxglove rendering. Falls back to grey for any class
# not listed here (typically 'other' if it ever sneaks past target_classes).
CLASS_COLORS: dict[str, tuple[float, float, float, float]] = {
    'aircraft': (1.0, 0.7, 0.1, 0.85),  # warm orange
    'tank':     (1.0, 0.25, 0.25, 0.85),  # red
}
DEFAULT_COLOR = (0.5, 0.5, 0.5, 0.7)


# ─── Config ────────────────────────────────────────────────────────────

CONFIG_PATH = Path(os.environ.get('LIDAR_CONFIG', '/app/config/pipelines/perception-lidar.yaml'))


@dataclass
class Config:
    model_variant: str
    confidence_threshold: float
    target_classes: list[str]
    input_type: str          # 'pointcloud2' (3D) or 'laserscan' (2D planar)
    input_topic: str
    output_topic: str
    marker_topic: str
    enable_tracking: bool


CONFIG_DEFAULTS = Config(
    model_variant='pointpillars',
    confidence_threshold=0.5,
    target_classes=['aircraft', 'tank'],
    input_type='pointcloud2',
    input_topic='/lidar/points',
    output_topic='/perception/lidar/detections',
    marker_topic='/perception/lidar/markers',
    enable_tracking=False,
)


VALID_INPUT_TYPES = ('pointcloud2', 'laserscan')


def load_config(path: Path = CONFIG_PATH, log: Optional[logging.Logger] = None) -> Config:
    if not path.is_file():
        if log:
            log.warning('config not found at %s; using defaults', path)
        return CONFIG_DEFAULTS
    with path.open() as f:
        raw = yaml.safe_load(f) or {}
    cls = list(raw.get('target_classes') or CONFIG_DEFAULTS.target_classes)
    input_type = str(raw.get('input_type', CONFIG_DEFAULTS.input_type)).lower()
    if input_type not in VALID_INPUT_TYPES:
        if log:
            log.warning(
                'unknown input_type=%r; falling back to %s', input_type, CONFIG_DEFAULTS.input_type
            )
        input_type = CONFIG_DEFAULTS.input_type
    return Config(
        model_variant=str(raw.get('model_variant', CONFIG_DEFAULTS.model_variant)),
        confidence_threshold=float(raw.get('confidence_threshold', CONFIG_DEFAULTS.confidence_threshold)),
        target_classes=[str(c) for c in cls],
        input_type=input_type,
        input_topic=str(raw.get('input_topic', CONFIG_DEFAULTS.input_topic)),
        output_topic=str(raw.get('output_topic', CONFIG_DEFAULTS.output_topic)),
        marker_topic=str(raw.get('marker_topic', CONFIG_DEFAULTS.marker_topic)),
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
    """Geometric mean of per-axis fit scores. Returns 0.0..1.0.

    Height contributes only when the input has a real z extent; 2D
    LaserScans set every point to z=0 by construction, so height-based
    scoring would force every detection's score to ~0. In that case the
    aspect ratio and footprint dimensions carry the discrimination on
    their own.
    """
    if bbox.width <= 0:
        return 0.0
    parts = [
        _within(bbox.length, prior.length),
        _within(bbox.width, prior.width),
        _within(bbox.length / max(bbox.width, 0.01), prior.length_over_width),
    ]
    if bbox.height > 0:
        parts.append(_within(bbox.height, prior.height))
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
            f'input_type={cfg.input_type}, '
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

        # Subscription type follows the configured input modality. The
        # downstream processing (DBSCAN → AABB → score → publish) is shared
        # between the two; the only difference is how we get N×3 points
        # from the incoming message.
        if cfg.input_type == 'laserscan':
            self.sub = self.create_subscription(
                LaserScan, cfg.input_topic, self._on_scan, _be_qos()
            )
        else:
            self.sub = self.create_subscription(
                PointCloud2, cfg.input_topic, self._on_cloud, _be_qos()
            )
        self.pub = self.create_publisher(
            LidarDetectionArray, cfg.output_topic, _be_qos()
        )
        # Foxglove Studio's 3D panel renders MarkerArray natively, so a
        # parallel marker stream gives an instant live visualisation
        # without a custom Studio panel.
        self.marker_pub = self.create_publisher(
            MarkerArray, cfg.marker_topic, _be_qos()
        )
        self.get_logger().info(
            f'subscribed to {cfg.input_topic} ({cfg.input_type}); '
            f'publishing detections to {cfg.output_topic} '
            f'and markers to {cfg.marker_topic}'
        )

    def _on_cloud(self, msg: PointCloud2) -> None:
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
        self._process(xyz, msg.header)

    def _on_scan(self, msg: LaserScan) -> None:
        # LaserScan → N×3 with z=0. Invalid returns (inf/NaN/out-of-range)
        # are filtered before projection so DBSCAN doesn't see them.
        n = len(msg.ranges)
        if n == 0:
            return
        angles = msg.angle_min + np.arange(n, dtype=np.float32) * msg.angle_increment
        ranges = np.asarray(msg.ranges, dtype=np.float32)
        valid = np.isfinite(ranges) & (ranges >= msg.range_min) & (ranges <= msg.range_max)
        if not np.any(valid):
            return
        xs = ranges[valid] * np.cos(angles[valid])
        ys = ranges[valid] * np.sin(angles[valid])
        zs = np.zeros_like(xs)
        xyz = np.column_stack([xs, ys, zs])
        self._process(xyz, msg.header)

    def _process(self, xyz: np.ndarray, header: Header) -> None:
        try:
            detections = self._detect_from_xyz(xyz, header)
        except Exception:
            self.get_logger().exception('detection failed; dropping frame')
            return

        out = LidarDetectionArray()
        out.header = header
        out.detections = detections
        self.pub.publish(out)
        self.marker_pub.publish(self._to_markers(detections, header))

    def _detect_from_xyz(self, xyz: np.ndarray, header: Header) -> list[LidarDetection]:
        if xyz.size == 0:
            return []

        # Ground + range filter. The ground filter is a no-op for 2D
        # LaserScans (all z=0 > GROUND_Z_THRESHOLD=-1.0); the range filter
        # still rejects far returns.
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
            det.header.stamp = header.stamp
            det.header.frame_id = header.frame_id
            det.class_id = label
            det.score = float(score)
            det.center = Point(x=bbox.cx, y=bbox.cy, z=bbox.cz)
            det.size = Vector3(x=bbox.length, y=bbox.width, z=bbox.height)
            det.track_id = 0
            out.append(det)
        return out

    def _to_markers(self, detections: list[LidarDetection], header: Header) -> MarkerArray:
        """Render the current frame as a MarkerArray for Foxglove's 3D panel.

        First entry is a DELETEALL so the previous frame's markers don't
        linger when this frame has fewer detections. Each surviving
        detection becomes one CUBE + one TEXT marker labelled with the
        class id and score. Marker IDs are stable within a frame; the
        DELETEALL guarantees correctness across frames.
        """
        markers: list[Marker] = []

        clear = Marker()
        clear.header = header
        clear.action = Marker.DELETEALL
        markers.append(clear)

        for i, det in enumerate(detections):
            r, g, b, a = CLASS_COLORS.get(det.class_id, DEFAULT_COLOR)
            color = ColorRGBA(r=r, g=g, b=b, a=a)

            cube = Marker()
            cube.header = header
            cube.ns = 'detections'
            cube.id = i
            cube.type = Marker.CUBE
            cube.action = Marker.ADD
            cube.pose.position = det.center
            cube.pose.orientation.w = 1.0
            # Minimum scale of 0.05 m so a degenerate (zero-extent on one
            # axis, e.g. 2D scan height) cube still renders as a thin slab
            # rather than disappearing.
            cube.scale.x = max(float(det.size.x), 0.05)
            cube.scale.y = max(float(det.size.y), 0.05)
            cube.scale.z = max(float(det.size.z), 0.05)
            cube.color = color
            markers.append(cube)

            text = Marker()
            text.header = header
            text.ns = 'detections_label'
            text.id = i
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose.position.x = float(det.center.x)
            text.pose.position.y = float(det.center.y)
            text.pose.position.z = float(det.center.z) + max(float(det.size.z), 0.05) / 2 + 0.5
            text.pose.orientation.w = 1.0
            text.scale.z = 1.0  # text height in metres
            text.color = ColorRGBA(r=1.0, g=1.0, b=1.0, a=1.0)
            text.text = f'{det.class_id} {det.score:.2f}'
            markers.append(text)

        out = MarkerArray()
        out.markers = markers
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
