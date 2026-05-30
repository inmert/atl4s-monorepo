"""Environment-driven configuration for the console (logic layer).

The console runs natively on the host (not in a container), so paths default to
locations relative to this package and can be overridden by env vars.
"""

import os
from pathlib import Path

# console/ (this file is console/api/config.py).
CONSOLE_ROOT = Path(__file__).resolve().parents[1]

CONSOLE_BIND = os.environ.get('CONSOLE_BIND', '0.0.0.0')
CONSOLE_PORT = int(os.environ.get('CONSOLE_PORT', '8089'))

# Built SPA (vite output). Override with CONSOLE_STATIC_DIR if built elsewhere.
STATIC_DIR = Path(os.environ.get('CONSOLE_STATIC_DIR') or (CONSOLE_ROOT / 'ui' / 'dist'))
