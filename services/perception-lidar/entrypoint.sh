#!/bin/bash
set -e

source /opt/ros/humble/setup.bash
source /workspace/install/setup.bash

echo "[entrypoint] Launching perception-lidar (config=${LIDAR_CONFIG})..."
exec python3 /lidar_detector.py
