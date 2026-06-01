# mesh-worker on the VM — Pub/Sub pull subscriber that runs alongside
# crackseg in docker-compose. Different entrypoint from the Cloud Run
# Dockerfile (which boots gunicorn + main.py).

FROM python:3.11-slim AS base

# Runtime libs for open3d + pyrealsense2 + Draco encoder (gltf-transform)
# + Open3D's OffscreenRenderer (EGL + Mesa software fallback).
# Package names match Debian trixie (python:3.11-slim's base).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libusb-1.0-0 \
    libegl1 \
    libegl-mesa0 \
    libosmesa6 \
    libx11-6 \
    libxrandr2 \
    libxinerama1 \
    libxcursor1 \
    ca-certificates \
    nodejs \
    npm \
 && rm -rf /var/lib/apt/lists/*

# gltf-transform for Draco compression of the mobile mesh variants
# (see docs/MOBILE_SHELL.md §2.2). Bundled here so the same image
# serves both the defect path and the future mobile-mesh build.
RUN npm install -g @gltf-transform/cli

WORKDIR /app

# Python deps in one layer for cache locality.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir google-cloud-pubsub

# Source. defects/ is a package directory — copy as such.
COPY main.py build_mesh.py vm_worker.py renders.py ./
COPY defects/ ./defects/

# VM-side healthcheck endpoint
EXPOSE 8080

# Pub/Sub pull subscriber. Cloud Run's gunicorn entrypoint is replaced
# by a single Python process that holds the subscription open.
CMD ["python", "vm_worker.py"]
