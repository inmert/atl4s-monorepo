#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

echo "[entrypoint] Launching foxglove_bridge on ${FOXGLOVE_ADDRESS}:${FOXGLOVE_PORT}..."
# params.yaml carries best_effort_qos_topic_whitelist so the bridge can absorb
# high-rate publishers without backpressure. Putting list params on the CLI
# via -p is fragile due to bash + ros2 quoting; the YAML file is reliable.
exec ros2 run foxglove_bridge foxglove_bridge \
    --ros-args \
    --params-file /params.yaml \
    -p port:="${FOXGLOVE_PORT}" \
    -p address:="${FOXGLOVE_ADDRESS}"
