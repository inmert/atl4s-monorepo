FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    git python3 python3-pip python3-dev python3-setuptools \
    python3-wheel python3-future python3-lxml \
    build-essential ccache g++ gawk \
    libtool libxml2-dev libxslt1-dev \
    wget curl rsync sudo \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --recurse-submodules --shallow-submodules \
    https://github.com/ArduPilot/ardupilot.git /ardupilot

WORKDIR /ardupilot

RUN pip3 install --no-cache-dir pymavlink MAVProxy pexpect future empy==3.3.4

RUN modules/waf/waf-light configure --board sitl \
    && modules/waf/waf-light copter

EXPOSE 14550/udp 14551/udp

CMD ["/bin/bash", "-c", "/ardupilot/build/sitl/bin/arducopter \
    --model quad \
    --home ${SITL_HOME_LAT:-37.6213},${SITL_HOME_LON:--122.3790},${SITL_HOME_ALT:-5},${SITL_HOME_HEADING:-0} \
    --defaults /ardupilot/Tools/autotest/default_params/copter.parm \
    --serial0 udpclient:127.0.0.1:14550 \
    --serial1 udpclient:127.0.0.1:14551"]
