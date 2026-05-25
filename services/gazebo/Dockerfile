# gazebo — Gazebo Harmonic + ArduPilot SITL plugin. Headless on the L4 GPU.
# Exposes the ArduPilot SITL plugin TCP/UDP ports for the sitl container to
# connect to in B.2.

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Tools + OSRF Gazebo apt repo.
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

# Build the ArduPilot Gazebo plugin (provides the iris model + SITL bridge).
# We keep the source tree so Gazebo can find models and worlds shipped with it.
RUN git clone --depth 1 https://github.com/ArduPilot/ardupilot_gazebo.git /ardupilot_gazebo \
    && cmake -S /ardupilot_gazebo -B /ardupilot_gazebo/build -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    && cmake --build /ardupilot_gazebo/build -j"$(nproc)"

# Custom worlds (ATL4S) layered on top of upstream models + worlds.
COPY world/ /atl4s/worlds/

# Gazebo discovery paths: ArduPilot plugin .so, ArduPilot stock models and
# worlds, our custom worlds.
ENV GZ_SIM_SYSTEM_PLUGIN_PATH=/ardupilot_gazebo/build
ENV GZ_SIM_RESOURCE_PATH=/ardupilot_gazebo/models:/ardupilot_gazebo/worlds:/atl4s/worlds

# Headless rendering via EGL on the NVIDIA driver mounted by the container
# toolkit. `graphics` and `compute` are what Gazebo needs.
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility

# World loaded by entrypoint; override per `docker compose` for ad-hoc scenes.
ENV GZ_WORLD=iris_runway.sdf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ArduPilot SITL plugin uses UDP for the FDM (flight dynamics) bridge.
# Default ports: 9002 (Gazebo→ArduPilot sensor stream), 9003 (ArduPilot→Gazebo actuators).
EXPOSE 9002/udp 9003/udp

CMD ["/entrypoint.sh"]
