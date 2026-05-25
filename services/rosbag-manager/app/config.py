"""Environment-driven configuration for rosbag-manager."""

import os
from pathlib import Path

BAG_DIR = Path(os.environ.get('BAG_DIR', '/data/bags'))
GCS_BUCKET = os.environ.get('GCS_BUCKET', 'atl4s-rosbags')

DEFAULT_RECORD_TOPICS = os.environ.get(
    'RECORD_TOPICS',
    '/mavros/state /mavros/battery /mavros/global_position/global '
    '/mavros/imu/data /camera/image /camera/camera_info /imu/gazebo /clock',
).split()
