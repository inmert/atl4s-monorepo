# dashboard — single human-facing surface for ATL4S. React + Vite + TS
# frontend, FastAPI + rclpy backend. Multi-stage: stage 1 builds the
# frontend, stage 2 runs uvicorn on top of ros:humble and serves the
# built assets.

FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json ./
COPY frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build


FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip \
        ros-humble-mavros-msgs \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
        fastapi==0.115.5 \
        uvicorn[standard]==0.32.0 \
        httpx==0.27.2 \
        python-multipart==0.0.12 \
        opencv-python-headless==4.10.0.84

ENV DASHBOARD_BIND=0.0.0.0
ENV DASHBOARD_PORT=8089
ENV ROSBAG_MANAGER_URL=http://127.0.0.1:8086

WORKDIR /app
COPY backend/ /app/backend/
COPY --from=frontend-build /app/frontend/dist /app/static/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
