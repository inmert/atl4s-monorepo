#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

ARGS=("fcu_url:=${FCU_URL}")
if [ -n "${GCS_URL}" ]; then
    ARGS+=("gcs_url:=${GCS_URL}")
fi

echo "[entrypoint] Launching mavros with: ${ARGS[*]}"
exec ros2 launch mavros apm.launch "${ARGS[@]}"
