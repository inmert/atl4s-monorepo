# Foxglove Bridge — exposes ROS 2 topics over WebSocket on TCP 8765
# for browser-based inspection in Foxglove Studio (studio.foxglove.dev).

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# mavros_msgs lets the bridge expose /mavros/* services (arming, set_mode,
# param/*) to Studio. Without it the bridge WARNs and only topics work.
# Add the -msgs package of every new service that exposes services.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-foxglove-bridge \
        ros-humble-mavros-msgs \
    && rm -rf /var/lib/apt/lists/*

ENV FOXGLOVE_PORT=8765
ENV FOXGLOVE_ADDRESS=0.0.0.0

EXPOSE 8765/tcp

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
