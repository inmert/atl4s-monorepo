# bag-record — records selected ROS 2 topics to an mcap bag under /data/bags.
# Topic list and bag name configurable via env. Designed to be brought up under
# the `record` profile and stopped via `docker stop` (graceful SIGTERM closes
# the bag cleanly).

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-rosbag2 \
        ros-humble-rosbag2-storage-mcap \
        ros-humble-mavros-msgs \
    && rm -rf /var/lib/apt/lists/*

ENV RECORD_TOPICS="/mavros/state /mavros/battery /mavros/global_position/global /mavros/imu/data /camera/image /camera/camera_info /imu/gazebo /clock"
ENV BAG_DIR=/data/bags

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
