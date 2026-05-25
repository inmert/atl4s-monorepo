#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

echo "[entrypoint] Launching foxglove_bridge on ${FOXGLOVE_ADDRESS}:${FOXGLOVE_PORT}..."
exec ros2 run foxglove_bridge foxglove_bridge \
    --ros-args \
    -p port:="${FOXGLOVE_PORT}" \
    -p address:="${FOXGLOVE_ADDRESS}"
