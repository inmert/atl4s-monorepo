#!/bin/bash
set -e

exec uvicorn app.main:app \
    --host "${CRACKSEG_BIND:-127.0.0.1}" \
    --port "${CRACKSEG_PORT:-8092}"
