# inspector — backend engine for 3D model + (soon) rosbag viewing and live ML.
# Backend-only: the viewer UI lives in the console, which proxies to this
# service. No ROS today (rosbag playback will go through rosbag-manager's HTTP
# API); GPU + ML deps get added here when live ML pipelines land.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir \
        fastapi==0.115.5 \
        "uvicorn[standard]==0.32.0" \
        python-multipart==0.0.12 \
        httpx==0.27.2

ENV INSPECTOR_BIND=127.0.0.1
ENV INSPECTOR_PORT=8091
ENV MODELS_DIR=/data/models

WORKDIR /app
COPY backend/ /app/backend/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
