#!/bin/bash
set -e

echo "[entrypoint] Gazebo Harmonic, world=${GZ_WORLD}"
echo "[entrypoint] GZ_SIM_SYSTEM_PLUGIN_PATH=${GZ_SIM_SYSTEM_PLUGIN_PATH}"
echo "[entrypoint] GZ_SIM_RESOURCE_PATH=${GZ_SIM_RESOURCE_PATH}"

# -s: server only (no GUI). -r: start the simulation immediately.
# --headless-rendering: EGL backend so camera/lidar sensors still render
# without an X display.
exec gz sim -s -r -v 3 --headless-rendering "${GZ_WORLD}"
