#!/bin/bash
set -e

# Forward SIGTERM/SIGINT to children so docker stop is clean.
trap 'kill $(jobs -p) 2>/dev/null; exit 0' SIGTERM SIGINT

echo "[entrypoint] Starting arducopter..."
/ardupilot/build/sitl/bin/arducopter \
    --model quad \
    --speedup "${SITL_SPEEDUP}" \
    --home "${SITL_HOME_LAT},${SITL_HOME_LON},${SITL_HOME_ALT},${SITL_HOME_HEADING}" \
    --base-port 5760 \
    &

echo "[entrypoint] Waiting for arducopter TCP 5760..."
for i in {1..30}; do
    if (echo > /dev/tcp/127.0.0.1/5760) 2>/dev/null; then
        echo "[entrypoint] arducopter is listening."
        break
    fi
    sleep 1
done

echo "[entrypoint] Starting MAVProxy, forwarding to ${MAVPROXY_OUT}..."
# Foreground, NOT --daemon — otherwise mavproxy double-forks, PID 1 exits,
# and the container restart-loops.
mavproxy.py \
    --master tcp:127.0.0.1:5760 \
    --out "${MAVPROXY_OUT}" \
    --non-interactive \
    --logfile /tmp/mavproxy.log &

# Exit if either process dies so the supervisor restarts the whole unit.
wait -n
echo "[entrypoint] One process exited. Shutting down."
kill $(jobs -p) 2>/dev/null || true
exit 1
