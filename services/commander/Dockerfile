# commander — autonomy node for ATL4S
# Subscribes to MAVROS telemetry, applies decision logic, will publish
# commands back to MAVROS as behaviors are added.

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
