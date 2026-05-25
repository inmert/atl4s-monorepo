#!/usr/bin/env python3
"""commander — first-cut autonomy node for ATL4S.

Subscribes to /mavros/battery and /mavros/state with Best Effort QoS
(matches what MAVROS offers). Logs threshold crossings and state
transitions, and on a low-battery latch calls /mavros/set_mode RTL.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from mavros_msgs.msg import State
from mavros_msgs.srv import SetMode
from sensor_msgs.msg import BatteryState


# 5% hysteresis above the low threshold before clearing the latch — avoids
# flapping when the battery hovers near the trip point.
BATTERY_HYSTERESIS = 0.05

# Mode commander switches to on a low-battery latch.
LOW_BATTERY_MODE = 'RTL'


def best_effort_qos(depth: int = 10) -> QoSProfile:
    return QoSProfile(depth=depth, reliability=ReliabilityPolicy.BEST_EFFORT)


class Commander(Node):
    def __init__(self) -> None:
        super().__init__('commander')

        self.declare_parameter('battery_low_threshold', 0.20)
        self.battery_low_threshold: float = (
            self.get_parameter('battery_low_threshold')
            .get_parameter_value()
            .double_value
        )

        self.low_battery_latched = False
        self.last_state: State | None = None

        qos = best_effort_qos()
        self.create_subscription(BatteryState, '/mavros/battery', self.on_battery, qos)
        self.create_subscription(State, '/mavros/state', self.on_state, qos)

        self.set_mode_client = self.create_client(SetMode, '/mavros/set_mode')

        self.get_logger().info(
            f'commander up. Watching /mavros/battery '
            f'(threshold {self.battery_low_threshold:.0%}, hysteresis {BATTERY_HYSTERESIS:.0%}) '
            f'and /mavros/state. Low-battery action: set_mode {LOW_BATTERY_MODE}.'
        )

    def on_battery(self, msg: BatteryState) -> None:
        pct = msg.percentage
        if pct <= self.battery_low_threshold and not self.low_battery_latched:
            self.low_battery_latched = True
            self.get_logger().warn(
                f'Battery low: {pct:.1%} <= {self.battery_low_threshold:.0%} '
                f'({msg.voltage:.2f} V). Triggering {LOW_BATTERY_MODE}.'
            )
            self._trigger_low_battery_mode()
        elif pct > self.battery_low_threshold + BATTERY_HYSTERESIS and self.low_battery_latched:
            self.low_battery_latched = False
            self.get_logger().info(f'Battery recovered: {pct:.1%}.')

    def on_state(self, msg: State) -> None:
        if self.last_state is None:
            self.get_logger().info(
                f'Initial state: connected={msg.connected}, mode={msg.mode}, armed={msg.armed}.'
            )
        else:
            if msg.connected != self.last_state.connected:
                self.get_logger().warn(
                    f'Connection: {self.last_state.connected} -> {msg.connected}.'
                )
            if msg.mode != self.last_state.mode:
                self.get_logger().info(f'Mode: {self.last_state.mode} -> {msg.mode}.')
            if msg.armed != self.last_state.armed:
                self.get_logger().warn(f'Armed: {self.last_state.armed} -> {msg.armed}.')
        self.last_state = msg

    def _trigger_low_battery_mode(self) -> None:
        if not self.set_mode_client.service_is_ready():
            self.get_logger().error(
                '/mavros/set_mode is not available; cannot trigger '
                f'{LOW_BATTERY_MODE}.'
            )
            return
        req = SetMode.Request()
        req.custom_mode = LOW_BATTERY_MODE
        future = self.set_mode_client.call_async(req)
        future.add_done_callback(self._on_set_mode_response)

    def _on_set_mode_response(self, future) -> None:
        try:
            response = future.result()
        except Exception as exc:
            self.get_logger().error(f'set_mode call raised: {exc}')
            return
        if response.mode_sent:
            self.get_logger().info(f'set_mode {LOW_BATTERY_MODE} accepted.')
        else:
            self.get_logger().error(
                f'set_mode {LOW_BATTERY_MODE} rejected by MAVROS '
                '(mode_sent=False; vehicle may not be in a state that allows it).'
            )


def main() -> None:
    rclpy.init()
    try:
        rclpy.spin(Commander())
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
