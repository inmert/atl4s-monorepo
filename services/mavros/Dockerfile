# MAVROS — bridges MAVLink (UDP) to ROS 2 topics.
# Listens on UDP 14550 for incoming MAVLink (from SITL/MAVProxy on the
# same host, or from the Orin Nano forwarded to the VM's public IP).

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-mavros \
        ros-humble-mavros-extras \
        ros-humble-mavros-msgs \
        geographiclib-tools \
        wget \
    && rm -rf /var/lib/apt/lists/*

# GeographicLib geoid data — required for accurate altitude conversion.
RUN wget -q https://raw.githubusercontent.com/mavlink/mavros/ros2/mavros/scripts/install_geographiclib_datasets.sh \
    && bash install_geographiclib_datasets.sh \
    && rm install_geographiclib_datasets.sh

# udp://@:14550 = bind on all interfaces, port 14550, accept any sender.
ENV FCU_URL="udp://@:14550"
ENV GCS_URL=""

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
