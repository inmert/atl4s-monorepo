#!/bin/bash
# Run the synthetic lidar publisher inside the perception-lidar image's
# environment (already has numpy + sensor_msgs_py and the FastDDS XML
# wired). Streams /lidar/points at ~5 Hz until Ctrl-C.
#
# Useful to drive perception-lidar end-to-end on a host with no real
# lidar source — see services/perception-lidar/README.md "Testing
# without real lidar".

set -e

cd "$(dirname "$0")/.."

docker run --rm -it \
    --network host \
    -v "$PWD/shared/fastdds_profiles.xml:/fastdds_profiles.xml:ro" \
    -v "$PWD/services/perception-lidar/test/publish_fake_lidar.py:/publish_fake_lidar.py:ro" \
    -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}" \
    -e FASTRTPS_DEFAULT_PROFILES_FILE=/fastdds_profiles.xml \
    --entrypoint bash \
    atl4s/perception-lidar:latest \
    -c "source /opt/ros/humble/setup.bash && exec python3 /publish_fake_lidar.py"
