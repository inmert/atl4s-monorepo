#!/bin/bash
set -e

# Forward SIGTERM/SIGINT to children so docker stop is clean.
trap 'kill $(jobs -p) 2>/dev/null; exit 0' SIGTERM SIGINT

echo "[entrypoint] Starting arducopter (model=JSON, FDM via Gazebo on UDP :9002)..."
# --model JSON delegates physics to the ardupilot_gazebo plugin. SITL_SPEEDUP
# is intentionally ignored — Gazebo's real_time_factor controls sim time.
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
# Foreground (no --daemon): mavproxy double-forks under --daemon, PID 1
# exits, and the container restart-loops.
# --streamrate drives /mavros/* topic rates; see HANDOFF "MAVProxy stream
# rate" for why this is the only knob in ArduCopter 4.8.
# stdout → /dev/null silences the per-second STATUSTEXT echoes
# ("Flight battery 100 percent" etc.) that otherwise flood docker logs;
# stderr stays attached so real errors are still surfaced. Full binary
# tlog is captured via --logfile if forensics are needed.
mavproxy.py \
    --master tcp:127.0.0.1:5760 \
    --out "${MAVPROXY_OUT}" \
    --streamrate "${MAVPROXY_STREAMRATE}" \
    --non-interactive \
    --logfile /tmp/mavproxy.log \
    >/dev/null &

# Exit if either process dies so Docker restarts the whole container.
wait -n
echo "[entrypoint] One process exited. Shutting down."
kill $(jobs -p) 2>/dev/null || true
exit 1
