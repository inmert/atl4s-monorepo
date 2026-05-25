#!/bin/bash
set -euo pipefail

EXPECTED=(
  /mavros/state
  /mavros/battery
  /mavros/global_position/global
  /mavros/imu/data
)

if ! docker inspect atl4s-mavros >/dev/null 2>&1; then
  echo "atl4s-mavros container is not running. Start the stack first." >&2
  exit 2
fi

TOPICS=$(docker exec atl4s-mavros bash -c \
  "source /opt/ros/humble/setup.bash && ros2 topic list")

missing=0
for topic in "${EXPECTED[@]}"; do
  if echo "$TOPICS" | grep -qx "$topic"; then
    echo "  OK   $topic"
  else
    echo "  MISS $topic"
    missing=$((missing + 1))
  fi
done

exit $missing
