# MAVROS — MAVLink (UDP) ⇄ ROS 2 topics. Binds UDP 14550.
# Source is the in-container MAVProxy under SITL, or the Orin Nano
# forwarding MAVLink to the VM's external IP in production.

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

# udp://[bind]@[remote] — bind side before the @. See README for the gotcha.
ENV FCU_URL="udp://:14550@"
ENV GCS_URL=""

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
