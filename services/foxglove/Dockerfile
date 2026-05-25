# Foxglove Bridge — exposes ROS 2 topics over WebSocket on TCP 8765
# for browser-based inspection in Foxglove Studio (studio.foxglove.dev).
#
# Built from the repo root so it can pick up shared/atl4s_msgs (see
# docker-compose.yml `context: .`).

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# mavros_msgs lets the bridge expose /mavros/* services (arming, set_mode,
# param/*) to Studio. Without it the bridge WARNs and only topics work.
# Add the -msgs package of every new service that exposes services.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-colcon-common-extensions \
        ros-humble-foxglove-bridge \
        ros-humble-mavros-msgs \
    && rm -rf /var/lib/apt/lists/*

# Build atl4s_msgs into /workspace/install/ so Studio can render
# /perception/lidar/detections and other atl4s_msgs/* topics. Entrypoint
# sources the overlay on top of /opt/ros/humble/setup.bash.
WORKDIR /workspace
COPY shared/atl4s_msgs /workspace/src/atl4s_msgs
RUN . /opt/ros/humble/setup.sh \
 && colcon build --packages-select atl4s_msgs --merge-install \
 && rm -rf /workspace/build /workspace/log

ENV FOXGLOVE_PORT=8765
ENV FOXGLOVE_ADDRESS=0.0.0.0

EXPOSE 8765/tcp

COPY services/foxglove/params.yaml /params.yaml
COPY services/foxglove/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
