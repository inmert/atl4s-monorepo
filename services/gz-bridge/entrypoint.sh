#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

echo "[entrypoint] Starting parameter_bridge with /bridge.yaml"
exec ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=/bridge.yaml
