# ArduPilot SITL with MAVProxy fan-out.
# arducopter master TCP :5760 → MAVProxy → UDP 127.0.0.1:14550 → MAVROS

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
        git python3 python3-pip python3-dev python3-setuptools \
        python3-wheel python3-future python3-lxml python3-numpy \
        python3-matplotlib python3-serial python3-scipy \
        build-essential ccache g++ gawk \
        libtool libxml2-dev libxslt1-dev \
        wget curl rsync procps \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --recurse-submodules --shallow-submodules \
        https://github.com/ArduPilot/ardupilot.git /ardupilot

WORKDIR /ardupilot

RUN pip3 install --no-cache-dir \
        pymavlink \
        MAVProxy \
        pexpect \
        future \
        empy==3.3.4

RUN modules/waf/waf-light configure --board sitl \
    && modules/waf/waf-light copter

ENV SITL_HOME_LAT=37.6213
ENV SITL_HOME_LON=-122.3790
ENV SITL_HOME_ALT=5
ENV SITL_HOME_HEADING=0
ENV SITL_SPEEDUP=1

# MAVProxy `--out` target. `udp:` is bidirectional (commands round-trip);
# `udpout:` is send-only and silently breaks commands from MAVROS.
ENV MAVPROXY_OUT=udp:127.0.0.1:14550

EXPOSE 5760/tcp 14550/udp

# MAVProxy `--streamrate` (Hz). MAVProxy requests data streams from ArduPilot
# via MAV_CMD_REQUEST_DATA_STREAM at this rate. Drives /mavros/* topic rates.
# Higher = richer telemetry but more MAVLink bandwidth + load on the FDM loop.
ENV MAVPROXY_STREAMRATE=10

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
