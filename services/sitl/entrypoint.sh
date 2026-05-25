#!/bin/bash
set -e

echo "[entrypoint] Starting arducopter..."
/ardupilot/build/sitl/bin/arducopter \
    --model quad \
    --speedup "${SITL_SPEEDUP}" \
    --home "${SITL_HOME_LAT},${SITL_HOME_LON},${SITL_HOME_ALT},${SITL_HOME_HEADING}" \
    --base-port 5760 \
    &

ARDUPILOT_PID=$!
echo "[entrypoint] arducopter PID=${ARDUPILOT_PID}"

# Wait a couple seconds for arducopter to open TCP 5760 before MAVProxy connects.
sleep 5

echo "[entrypoint] Starting MAVProxy, forwarding to ${MAVPROXY_OUT}..."
exec mavproxy.py \
    --master tcp:127.0.0.1:5760 \
    --out "${MAVPROXY_OUT}" \
    --daemon \
    --non-interactive \
    --logfile /tmp/mavproxy.log
