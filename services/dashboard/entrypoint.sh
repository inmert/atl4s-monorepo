#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

exec uvicorn backend.main:app \
    --host "${DASHBOARD_BIND}" \
    --port "${DASHBOARD_PORT}"
