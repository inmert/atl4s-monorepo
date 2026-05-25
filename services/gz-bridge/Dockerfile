# gz-bridge — ros_gz_bridge for Gazebo Harmonic ↔ ROS 2 Humble.
# Maps the Gazebo camera/IMU/GPS topics emitted by the iris model in
# services/gazebo to stable ROS 2 names (/camera/image, /camera/imu, …)
# so downstream services (foxglove, bag-record, perception) consume
# them under names that don't change when the world or model changes.

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# OSRF apt repo for the Harmonic-specific bridge package.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg lsb-release ca-certificates \
    && curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
        -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/gazebo-stable.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-ros-gzharmonic \
    && rm -rf /var/lib/apt/lists/*

COPY bridge.yaml /bridge.yaml
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
