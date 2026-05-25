#!/bin/bash
set -e

echo "[entrypoint] bag-web → gs://${GCS_BUCKET}, listening on :${BAG_WEB_PORT}..."
exec uvicorn bag_web:app \
    --host 0.0.0.0 \
    --port "${BAG_WEB_PORT}" \
    --no-access-log
