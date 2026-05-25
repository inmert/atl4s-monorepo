# perception-lidar — subscribes to a PointCloud2 input topic, classifies
# clusters into the configured target_classes, publishes
# atl4s_msgs/LidarDetectionArray.
#
# Built from the repo root so it can pick up shared/atl4s_msgs alongside
# its own source. The dashboard's pipeline registry expects the container
# to be named atl4s-perception-lidar and to read its runtime config from
# config/pipelines/perception-lidar.yaml (bind-mounted at runtime).

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip \
        python3-colcon-common-extensions \
        ros-humble-sensor-msgs-py \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
        numpy==1.26.4 \
        scikit-learn==1.5.2 \
        pyyaml==6.0.2

WORKDIR /workspace
COPY shared/atl4s_msgs /workspace/src/atl4s_msgs

# Build atl4s_msgs once and stash the install/ overlay; the entrypoint
# sources it on top of the ROS underlay. `--merge-install` keeps the
# layout flat (single install/ dir, not per-package).
RUN . /opt/ros/humble/setup.sh \
 && colcon build --packages-select atl4s_msgs --merge-install \
 && rm -rf /workspace/build /workspace/log

COPY services/perception-lidar/lidar_detector.py /lidar_detector.py
COPY services/perception-lidar/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /lidar_detector.py

ENV LIDAR_CONFIG=/app/config/pipelines/perception-lidar.yaml

CMD ["/entrypoint.sh"]
