"""Environment-driven configuration for the dashboard."""

import os
from pathlib import Path

ROSBAG_MANAGER_URL = os.environ.get('ROSBAG_MANAGER_URL', 'http://127.0.0.1:8086')

STATIC_DIR = Path(os.environ.get('DASHBOARD_STATIC_DIR', '/app/static'))
