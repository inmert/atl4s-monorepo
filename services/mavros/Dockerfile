# MAVROS — bridges MAVLink (UDP) to ROS 2 topics.
# Identical configuration for SITL on localhost or real drone via Orin.

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-mavros \
    ros-humble-mavros-extras \
    ros-humble-mavros-msgs \
    geographiclib-tools \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://raw.githubusercontent.com/mavlink/mavros/ros2/mavros/scripts/install_geographiclib_datasets.sh \
    && bash install_geographiclib_datasets.sh \
    && rm install_geographiclib_datasets.sh

ENV FCU_URL="udp://@:14550"
ENV GCS_URL=""

# Only append gcs_url:=... when GCS_URL is non-empty; otherwise mavros uses its default.
CMD ["bash", "-c", "if [ -n \"$GCS_URL\" ]; then ros2 launch mavros apm.launch fcu_url:=${FCU_URL} gcs_url:=${GCS_URL}; else ros2 launch mavros apm.launch fcu_url:=${FCU_URL}; fi"]
