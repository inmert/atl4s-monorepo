#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

echo "[entrypoint] Launching healthcheck (report=${HEALTHCHECK_REPORT_INTERVAL}s, http=:${HEALTHCHECK_HTTP_PORT})..."
exec python3 /healthcheck_node.py \
    --ros-args \
    -p report_interval_s:="${HEALTHCHECK_REPORT_INTERVAL}" \
    -p http_port:="${HEALTHCHECK_HTTP_PORT}"
