"""Environment-driven configuration for the inspector (backend engine)."""

import os
from pathlib import Path

# Bound to loopback by default — the console (on the host) proxies to it; the
# inspector is not exposed to browsers directly.
INSPECTOR_BIND = os.environ.get('INSPECTOR_BIND', '127.0.0.1')
INSPECTOR_PORT = int(os.environ.get('INSPECTOR_PORT', '8091'))

# Uploaded 3D models live here (bind-mounted from ./data/models).
MODELS_DIR = Path(os.environ.get('MODELS_DIR', '/data/models'))

# rosbag-manager (loopback) backs the rosbag features for now; the inspector
# will absorb its record/replay/GCS logic later.
ROSBAG_MANAGER_URL = os.environ.get('ROSBAG_MANAGER_URL', 'http://127.0.0.1:8086').rstrip('/')

# Model formats accepted for upload. The viewer renders fbx/glb/gltf today;
# obj/stl/ply are accepted for storage and will render as support lands.
ALLOWED_EXT = {'.fbx', '.glb', '.gltf', '.obj', '.stl', '.ply'}
