# dashboard — single human-facing surface for ATL4S. React + Vite + TS
# frontend, FastAPI + rclpy backend. Multi-stage: stage 1 builds the
# frontend, stage 2 colcon-builds custom message packages and runs
# uvicorn on top of ros:humble.
#
# Built from the repo root so it can pick up shared/atl4s_msgs alongside
# its own source (see docker-compose.yml `context: .`).

FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY services/dashboard/frontend/package.json ./
COPY services/dashboard/frontend/package-lock.json* ./
RUN npm install

COPY services/dashboard/frontend/ ./
RUN npm run build


FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip \
        python3-colcon-common-extensions \
        ros-humble-mavros-msgs \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
        fastapi==0.115.5 \
        uvicorn[standard]==0.32.0 \
        httpx==0.27.2 \
        python-multipart==0.0.12 \
        opencv-python-headless==4.10.0.84 \
        pyyaml==6.0.2 \
        docker==7.1.0

# Build atl4s_msgs into /workspace/install/ so the rclpy bridge can
# resolve atl4s_msgs/* types when the ROS page samples
# /perception/lidar/detections and friends. Entrypoint sources the
# overlay before launching uvicorn.
WORKDIR /workspace
COPY shared/atl4s_msgs /workspace/src/atl4s_msgs
RUN . /opt/ros/humble/setup.sh \
 && colcon build --packages-select atl4s_msgs --merge-install \
 && rm -rf /workspace/build /workspace/log

ENV DASHBOARD_BIND=0.0.0.0
ENV DASHBOARD_PORT=8089
ENV ROSBAG_MANAGER_URL=http://127.0.0.1:8086
ENV ROBOTS_CONFIG=/app/config/robots.yaml

WORKDIR /app
COPY services/dashboard/backend/ /app/backend/
COPY services/dashboard/config/ /app/config/
COPY --from=frontend-build /app/frontend/dist /app/static/
COPY services/dashboard/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
