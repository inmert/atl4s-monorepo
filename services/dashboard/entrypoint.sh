#!/bin/bash
set -e

source /opt/ros/humble/setup.bash
source /workspace/install/setup.bash

exec uvicorn backend.main:app \
    --host "${DASHBOARD_BIND}" \
    --port "${DASHBOARD_PORT}"
