"""Environment-driven configuration for rosbag-manager."""

import os
from pathlib import Path

BAG_DIR = Path(os.environ.get('BAG_DIR', '/data/bags'))
GCS_BUCKET = os.environ.get('GCS_BUCKET', 'atl4s-rosbags')
