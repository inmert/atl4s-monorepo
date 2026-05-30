#!/bin/bash
set -e

mkdir -p "${MODELS_DIR:-/data/models}"

exec uvicorn backend.main:app \
    --host "${INSPECTOR_BIND:-0.0.0.0}" \
    --port "${INSPECTOR_PORT:-8091}"
