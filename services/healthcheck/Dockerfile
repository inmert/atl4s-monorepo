# healthcheck — periodic topic-liveness monitor. Subscribes to a tracked set
# of MAVROS + gz-bridge topics, surfaces status to stdout, HTTP /health, and
# /atl4s/health (diagnostic_msgs/DiagnosticArray).

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# mavros_msgs for State.connected; diagnostic_msgs for the output topic.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-mavros-msgs \
        ros-humble-diagnostic-msgs \
    && rm -rf /var/lib/apt/lists/*

# Float syntax matters: `--ros-args -p key:=value` parses value as YAML.
# `5` is INTEGER, won't bind to a DOUBLE param.
ENV HEALTHCHECK_REPORT_INTERVAL=5.0
ENV HEALTHCHECK_HTTP_PORT=8088

COPY healthcheck_node.py /healthcheck_node.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /healthcheck_node.py

EXPOSE 8088/tcp

CMD ["/entrypoint.sh"]
