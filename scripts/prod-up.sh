#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Ensure SITL is not running in production (it may be left over from dev-up).
docker compose --profile sim stop sitl >/dev/null 2>&1 || true

docker compose up -d
docker compose ps
