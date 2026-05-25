#!/bin/bash
# Record SECONDS of topics to a bag, stop cleanly, wait for bag-uploader to finish.
# Usage: bag-record.sh [seconds] [bag-name]
# Defaults: 30 seconds, atl4s-<UTC timestamp>.

set -euo pipefail

cd "$(dirname "$0")/.."

SECONDS_TO_RECORD="${1:-30}"
BAG_NAME="${2:-atl4s-$(date -u +%Y%m%d-%H%M%S)}"

export BAG_NAME

echo "[bag-record] recording for ${SECONDS_TO_RECORD}s as ${BAG_NAME}"
docker compose --profile sim --profile record up -d bag-record bag-uploader

sleep "${SECONDS_TO_RECORD}"

echo "[bag-record] stopping recorder"
docker compose stop bag-record

echo "[bag-record] waiting for bag-uploader to push (stable window + upload)"
local_dir="./data/bags/${BAG_NAME}"
for _ in $(seq 1 60); do
  if [[ -f "${local_dir}.uploaded" ]]; then
    echo "[bag-record] uploaded: gs://${GCS_BUCKET:-atl4s-rosbags}/${BAG_NAME}/"
    exit 0
  fi
  sleep 2
done

echo "[bag-record] upload did not complete within 120s; check 'docker compose logs bag-uploader'" >&2
exit 1
