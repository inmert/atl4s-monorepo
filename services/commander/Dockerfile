# commander — autonomy node. Subscribes to MAVROS telemetry and calls
# MAVROS services in response.

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-mavros-msgs \
    && rm -rf /var/lib/apt/lists/*

ENV BATTERY_LOW_THRESHOLD=0.20

COPY commander_node.py /commander_node.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /commander_node.py

CMD ["/entrypoint.sh"]
