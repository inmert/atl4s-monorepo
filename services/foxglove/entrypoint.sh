#!/bin/bash
set -e

source /opt/ros/humble/setup.bash
source /workspace/install/setup.bash

echo "[entrypoint] Launching foxglove_bridge on ${FOXGLOVE_ADDRESS}:${FOXGLOVE_PORT}..."
# best_effort_qos_topic_whitelist is a list — fragile to pass through bash +
# ros2 -p quoting; carry it in params.yaml instead.
exec ros2 run foxglove_bridge foxglove_bridge \
    --ros-args \
    --params-file /params.yaml \
    -p port:="${FOXGLOVE_PORT}" \
    -p address:="${FOXGLOVE_ADDRESS}"
