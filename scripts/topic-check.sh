#!/bin/bash
set -e

EXPECTED=(
  "/mavros/state"
  "/mavros/battery"
  "/mavros/global_position/global"
  "/mavros/imu/data"
)

TOPICS=$(docker exec atl4s-mavros bash -c "source /opt/ros/humble/setup.bash && ros2 topic list")

for topic in "${EXPECTED[@]}"; do
  if echo "$TOPICS" | grep -qx "$topic"; then
    echo "  OK   $topic"
  else
    echo "  MISS $topic"
  fi
done
