#!/usr/bin/env python3
"""healthcheck — periodic liveness monitor for the ATL4S pipeline.

Surfaces:
- stdout one-line summary (docker logs atl4s-healthcheck)
- HTTP GET /health on HEALTHCHECK_HTTP_PORT — JSON body + 200/503
- diagnostic_msgs/DiagnosticArray on /atl4s/health (Foxglove panel renders it)
"""

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from mavros_msgs.msg import State as MavrosState
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import BatteryState, Image, Imu, NavSatFix


@dataclass
class TopicTrack:
    name: str
    msg_type: type
    max_stale_s: float
    required: bool
    last_seen: float = 0.0
    window: deque = field(default_factory=lambda: deque(maxlen=200))
    extra: str = ''


# Optional topics WARN instead of ERROR when stale, so prod runs without
# the sim profile (no /imu/gazebo, /clock, /camera/image) stay OK overall.
def tracked_defaults() -> list[TopicTrack]:
    return [
        TopicTrack('/mavros/state',                  MavrosState,  5.0,  True),
        TopicTrack('/mavros/battery',                BatteryState, 5.0,  True),
        TopicTrack('/mavros/global_position/global', NavSatFix,    10.0, True),
        TopicTrack('/mavros/imu/data',               Imu,          3.0,  True),
        TopicTrack('/imu/gazebo',                    Imu,          1.0,  False),
        TopicTrack('/clock',                         Clock,        1.0,  False),
        TopicTrack('/camera/image',                  Image,        2.0,  False),
    ]


def best_effort_qos(depth: int = 10) -> QoSProfile:
    return QoSProfile(depth=depth, reliability=ReliabilityPolicy.BEST_EFFORT)


class Healthcheck(Node):

    def __init__(self) -> None:
        super().__init__('healthcheck')

        self.declare_parameter('report_interval_s', 5.0)
        self.report_interval_s: float = (
            self.get_parameter('report_interval_s').get_parameter_value().double_value
        )

        self.declare_parameter('http_port', 8088)
        self.http_port: int = (
            self.get_parameter('http_port').get_parameter_value().integer_value
        )

        self.lock = threading.Lock()
        self.topics: dict[str, TopicTrack] = {t.name: t for t in tracked_defaults()}

        qos = best_effort_qos()
        for t in self.topics.values():
            # `name=t.name` binds the value per iteration; bare `t.name` in
            # the lambda would close over the loop variable.
            self.create_subscription(
                t.msg_type, t.name,
                lambda msg, name=t.name: self.on_msg(name, msg),
                qos,
            )

        self.diag_pub = self.create_publisher(DiagnosticArray, '/atl4s/health', 10)
        self.create_timer(self.report_interval_s, self.tick)
        self._start_http_server()

        self.get_logger().info(
            f'healthcheck up. Tracking {len(self.topics)} topics; '
            f'report every {self.report_interval_s:.1f}s; '
            f'HTTP /health on :{self.http_port}; publishing /atl4s/health.'
        )

    def on_msg(self, name: str, msg) -> None:
        now = time.monotonic()
        with self.lock:
            t = self.topics[name]
            t.last_seen = now
            t.window.append(now)
            if name == '/mavros/state':
                t.extra = 'connected' if msg.connected else 'disconnected'

    def evaluate(self):
        now = time.monotonic()
        per_topic: list[dict] = []
        overall = DiagnosticStatus.OK

        with self.lock:
            for t in self.topics.values():
                if t.last_seen == 0.0:
                    stale_s = None
                    level = DiagnosticStatus.ERROR if t.required else DiagnosticStatus.WARN
                    msg = 'no messages received yet'
                else:
                    stale_s = now - t.last_seen
                    if stale_s > t.max_stale_s:
                        level = DiagnosticStatus.ERROR if t.required else DiagnosticStatus.WARN
                        msg = f'stale {stale_s:.1f}s (> {t.max_stale_s:.1f}s)'
                    else:
                        level = DiagnosticStatus.OK
                        msg = 'fresh'

                if t.name == '/mavros/state' and t.extra == 'disconnected':
                    level = DiagnosticStatus.ERROR
                    msg = 'MAVLink disconnected'

                rate_hz = _rolling_rate(t.window, now, t.max_stale_s)

                per_topic.append({
                    'name': t.name,
                    'level': _level_name(level),
                    'msg': msg,
                    'stale_s': round(stale_s, 2) if stale_s is not None else None,
                    'rate_hz': round(rate_hz, 2),
                    'required': t.required,
                })

                if level > overall:
                    overall = level

        return overall, per_topic

    def tick(self) -> None:
        overall, per_topic = self.evaluate()
        self._publish_diagnostic(overall, per_topic)
        self._log_summary(overall, per_topic)

    def _publish_diagnostic(self, overall, per_topic: list[dict]) -> None:
        arr = DiagnosticArray()
        arr.header.stamp = self.get_clock().now().to_msg()
        for entry in per_topic:
            s = DiagnosticStatus()
            s.level = _level_byte(entry['level'])
            s.name = entry['name']
            s.message = entry['msg']
            s.hardware_id = 'atl4s-pipeline'
            for k in ('stale_s', 'rate_hz', 'required'):
                kv = KeyValue()
                kv.key = k
                kv.value = str(entry[k])
                s.values.append(kv)
            arr.status.append(s)
        self.diag_pub.publish(arr)

    def _log_summary(self, overall, per_topic: list[dict]) -> None:
        overall_name = _level_name(overall)
        ok = sum(1 for t in per_topic if t['level'] == 'OK')
        bad = [t for t in per_topic if t['level'] != 'OK']
        if bad:
            issues = ', '.join(f"{t['name']} {t['level']} {t['msg']}" for t in bad)
            self.get_logger().warn(
                f'[{overall_name}] {ok}/{len(per_topic)} fresh — {issues}'
            )
        else:
            rates = ' '.join(f"{_short(t['name'])}={t['rate_hz']:.1f}" for t in per_topic)
            self.get_logger().info(f'[{overall_name}] {ok}/{len(per_topic)} fresh — {rates}')

    def _start_http_server(self) -> None:
        node = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.rstrip('/') != '/health':
                    self.send_response(404)
                    self.end_headers()
                    return
                overall, per_topic = node.evaluate()
                overall_name = _level_name(overall)
                body = json.dumps({
                    'status': overall_name,
                    'checked_at': time.time(),
                    'topics': per_topic,
                }, indent=2).encode()
                self.send_response(200 if overall_name == 'OK' else 503)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args, **_kwargs):
                pass

        server = ThreadingHTTPServer(('0.0.0.0', self.http_port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()


def _rolling_rate(window: deque, now: float, max_stale_s: float) -> float:
    if len(window) < 2:
        return 0.0
    if now - window[-1] > max_stale_s:
        return 0.0
    span = window[-1] - window[0]
    return (len(window) - 1) / span if span > 0 else 0.0


# DiagnosticStatus.{OK,WARN,ERROR,STALE} are bytes in rclpy (b'\x00' ..),
# so the lookup keys here are bytes too — no conversion needed.
_LEVEL_NAMES = {
    DiagnosticStatus.OK: 'OK',
    DiagnosticStatus.WARN: 'WARN',
    DiagnosticStatus.ERROR: 'ERROR',
    DiagnosticStatus.STALE: 'STALE',
}
_LEVEL_BYTES = {v: k for k, v in _LEVEL_NAMES.items()}


def _level_name(level) -> str:
    return _LEVEL_NAMES.get(level, 'UNKNOWN')


def _level_byte(level_name: str):
    return _LEVEL_BYTES[level_name]


def _short(name: str) -> str:
    return name.rsplit('/', 1)[-1] or name


def main() -> None:
    rclpy.init()
    try:
        rclpy.spin(Healthcheck())
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
