# rosbag-manager — HTTP API for bag-plane operations: record, upload to GCS,
# GCS browser, and replay via ros2 bag play. Binds 127.0.0.1:8086 by default;
# the dashboard fronts it with HTTP Basic.

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip \
        ros-humble-rosbag2 \
        ros-humble-rosbag2-storage-mcap \
        ros-humble-mavros-msgs \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
        fastapi==0.115.5 \
        uvicorn[standard]==0.32.0 \
        google-cloud-storage==2.18.2 \
        python-multipart==0.0.12

ENV BAG_DIR=/data/bags
ENV GCS_BUCKET=atl4s-rosbags
ENV ROSBAG_MANAGER_BIND=127.0.0.1
ENV ROSBAG_MANAGER_PORT=8086

WORKDIR /app
COPY app/ /app/app/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
