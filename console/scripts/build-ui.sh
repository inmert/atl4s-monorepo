#!/usr/bin/env bash
# Build the console SPA to ui/dist using an ephemeral node:20 container, so the
# host needs no Node toolchain. Runs as the current uid/gid (HOME=/tmp keeps
# npm's cache out of a root-owned home) so the output isn't root-owned.
set -euo pipefail

CONSOLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Building console UI via node:20 (ephemeral container)…"
docker run --rm \
    -u "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -e npm_config_cache=/tmp/.npm \
    -v "$CONSOLE_DIR/ui":/app \
    -w /app \
    node:20-slim \
    bash -lc "npm install && npm run build"

echo "UI built -> $CONSOLE_DIR/ui/dist"
