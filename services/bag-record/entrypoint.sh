#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

mkdir -p "${BAG_DIR}"

NAME="${BAG_NAME:-atl4s-$(date -u +%Y%m%d-%H%M%S)}"
OUT="${BAG_DIR}/${NAME}"

# Generate a per-topic Best Effort QoS override file. `/mavros/*` publishers
# offer Best Effort; the default ros2 bag record subscription is Reliable
# and would silently miss every message. There is no wildcard in the YAML
# format, so each recorded topic needs its own entry.
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

# exec so SIGTERM (docker stop) reaches ros2 bag record directly, which
# closes the bag cleanly. A bash wrapper would catch the signal first and
# leave the bag mid-write.
exec ros2 bag record \
    --output "${OUT}" \
    --storage mcap \
    --qos-profile-overrides-path "${QOS_FILE}" \
    ${RECORD_TOPICS}
