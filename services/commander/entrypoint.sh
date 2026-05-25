#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

echo "[entrypoint] Launching commander (battery_low_threshold=${BATTERY_LOW_THRESHOLD})..."
exec python3 /commander_node.py \
    --ros-args -p battery_low_threshold:="${BATTERY_LOW_THRESHOLD}"
