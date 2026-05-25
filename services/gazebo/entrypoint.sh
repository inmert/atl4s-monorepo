#!/bin/bash
set -e

echo "[entrypoint] Gazebo Harmonic, world=${GZ_WORLD}"
echo "[entrypoint] GZ_SIM_SYSTEM_PLUGIN_PATH=${GZ_SIM_SYSTEM_PLUGIN_PATH}"
echo "[entrypoint] GZ_SIM_RESOURCE_PATH=${GZ_SIM_RESOURCE_PATH}"

# --headless-rendering uses the EGL backend so sensor cameras still render
# without an X display (the container has no display).
exec gz sim -s -r -v 3 --headless-rendering "${GZ_WORLD}"
