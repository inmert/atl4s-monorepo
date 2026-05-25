#!/bin/bash
set -e

# Forward SIGTERM/SIGINT to children so docker stop is clean.
trap 'kill $(jobs -p) 2>/dev/null; exit 0' SIGTERM SIGINT

echo "[entrypoint] Starting arducopter (model=JSON, FDM via Gazebo on UDP :9002)..."
# --model JSON: take physics from the external Gazebo ardupilot_gazebo plugin.
# Speedup is omitted on purpose — Gazebo's real_time_factor controls sim time.
/ardupilot/build/sitl/bin/arducopter \
    --model JSON \
    --defaults /ardupilot/Tools/autotest/default_params/copter.parm,/ardupilot/Tools/autotest/default_params/gazebo-iris.parm \
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

echo "[entrypoint] Starting MAVProxy (streamrate=${MAVPROXY_STREAMRATE} Hz), forwarding to ${MAVPROXY_OUT}..."
# Foreground, NOT --daemon — otherwise mavproxy double-forks, PID 1 exits,
# and the container restart-loops.
# --streamrate: rate MAVProxy requests SERIAL0 streams from ArduPilot via
# MAV_CMD_REQUEST_DATA_STREAM. Drives /mavros/* topic rates downstream.
# (ArduPilot 4.8 dropped the per-channel SR0_* params for SERIAL0 — the
# stream-rate path now goes through this CLI flag instead.)
mavproxy.py \
    --master tcp:127.0.0.1:5760 \
    --out "${MAVPROXY_OUT}" \
    --streamrate "${MAVPROXY_STREAMRATE}" \
    --non-interactive \
    --logfile /tmp/mavproxy.log &

# Exit if either process dies so the supervisor restarts the whole unit.
wait -n
echo "[entrypoint] One process exited. Shutting down."
kill $(jobs -p) 2>/dev/null || true
exit 1
