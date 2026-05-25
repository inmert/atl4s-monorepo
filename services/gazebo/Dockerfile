# gazebo — Gazebo Harmonic + ArduPilot SITL plugin. Headless on the L4 GPU.
# The sitl container connects to the plugin's UDP FDM channel.

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg lsb-release ca-certificates tzdata \
    && curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
        -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/gazebo-stable.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        gz-harmonic \
        libgz-sim8-dev \
        rapidjson-dev \
        libopencv-dev \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev \
        build-essential cmake git pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Source tree kept after build: GZ_SIM_RESOURCE_PATH points at it for the
# iris model and shipped worlds.
RUN git clone --depth 1 https://github.com/ArduPilot/ardupilot_gazebo.git /ardupilot_gazebo \
    && cmake -S /ardupilot_gazebo -B /ardupilot_gazebo/build -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    && cmake --build /ardupilot_gazebo/build -j"$(nproc)"

COPY world/ /atl4s/worlds/

ENV GZ_SIM_SYSTEM_PLUGIN_PATH=/ardupilot_gazebo/build
ENV GZ_SIM_RESOURCE_PATH=/ardupilot_gazebo/models:/ardupilot_gazebo/worlds:/atl4s/worlds

# `graphics` is required for the EGL headless renderer; `compute` for the
# CUDA path some Ogre2 components fall through.
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility

ENV GZ_WORLD=iris_runway.sdf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 9002: Gazebo → ArduPilot (FDM sensor stream). 9003: ArduPilot → Gazebo (servos).
EXPOSE 9002/udp 9003/udp

CMD ["/entrypoint.sh"]
