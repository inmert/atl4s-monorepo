#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

exec uvicorn app.main:app \
    --host "${ROSBAG_MANAGER_BIND}" \
    --port "${ROSBAG_MANAGER_PORT}"
