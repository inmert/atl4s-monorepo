#!/bin/bash
set -e

# Trap signals so both processes shut down cleanly on docker stop.
trap 'kill $(jobs -p) 2>/dev/null; exit 0' SIGTERM SIGINT

echo "[entrypoint] Starting arducopter..."
/ardupilot/build/sitl/bin/arducopter \
    --model quad \
    --speedup "${SITL_SPEEDUP}" \
    --home "${SITL_HOME_LAT},${SITL_HOME_LON},${SITL_HOME_ALT},${SITL_HOME_HEADING}" \
    --base-port 5760 \
    &

ARDU_PID=$!
echo "[entrypoint] arducopter PID=${ARDU_PID}"

# Wait for arducopter's TCP master to be ready.
echo "[entrypoint] Waiting for arducopter TCP 5760..."
for i in {1..30}; do
    if (echo > /dev/tcp/127.0.0.1/5760) 2>/dev/null; then
        echo "[entrypoint] arducopter is listening."
        break
    fi
    sleep 1
done

echo "[entrypoint] Starting MAVProxy, forwarding to ${MAVPROXY_OUT}..."

# NO --daemon: keep mavproxy in the foreground so the container stays alive.
# --non-interactive: disable the prompt.
# --logfile /tmp/mavproxy.log: capture mavproxy's internal logs.
mavproxy.py \
    --master tcp:127.0.0.1:5760 \
    --out "${MAVPROXY_OUT}" \
    --non-interactive \
    --logfile /tmp/mavproxy.log &

MAVP_PID=$!
echo "[entrypoint] MAVProxy PID=${MAVP_PID}"

# Wait on either process; exit if either dies.
wait -n
echo "[entrypoint] One process exited. Shutting down."
kill $(jobs -p) 2>/dev/null || true
exit 1
