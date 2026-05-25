#!/bin/bash
# Run the synthetic 2D LaserScan publisher inside the perception-lidar
# image's environment. Streams /lidar/scan at ~5 Hz until Ctrl-C.
#
# Use when perception-lidar's input_type is set to "laserscan" — drives
# the 2D path end-to-end on a host with no real planar lidar.

set -e

cd "$(dirname "$0")/.."

docker run --rm -it \
    --network host \
    -v "$PWD/shared/fastdds_profiles.xml:/fastdds_profiles.xml:ro" \
    -v "$PWD/services/perception-lidar/test/publish_fake_scan.py:/publish_fake_scan.py:ro" \
    -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}" \
    -e FASTRTPS_DEFAULT_PROFILES_FILE=/fastdds_profiles.xml \
    --entrypoint bash \
    atl4s/perception-lidar:latest \
    -c "source /opt/ros/humble/setup.bash && exec python3 /publish_fake_scan.py"
