#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

mkdir -p "${BAG_DIR}"

NAME="${BAG_NAME:-atl4s-$(date -u +%Y%m%d-%H%M%S)}"
OUT="${BAG_DIR}/${NAME}"

# BE override per topic. ros2 bag record subscribes Reliable by default
# and would silently miss every Best Effort publisher (most of /mavros/*).
# The YAML format takes `topic: <dict>`, not a list — no wildcards either.
QOS_FILE="/tmp/qos-overrides.yaml"
: > "${QOS_FILE}"
for topic in ${RECORD_TOPICS}; do
    cat >>"${QOS_FILE}" <<EOF
${topic}:
  history: keep_last
  depth: 100
  reliability: best_effort
  durability: volatile
EOF
done

echo "[entrypoint] Recording to ${OUT}"
echo "[entrypoint] Topics: ${RECORD_TOPICS}"

# exec, not run-and-wait: keeps ros2 bag record as PID 1 so SIGTERM from
# `docker stop` closes the bag cleanly instead of cutting it mid-write.
exec ros2 bag record \
    --output "${OUT}" \
    --storage mcap \
    --qos-profile-overrides-path "${QOS_FILE}" \
    ${RECORD_TOPICS}
