#!/bin/bash
# Record SECONDS of topics via the rosbag-manager API, then wait for the
# upload to complete.
# Usage: bag-record.sh [seconds] [bag-name]
# Defaults: 30 seconds, atl4s-<UTC timestamp>.

set -euo pipefail

cd "$(dirname "$0")/.."

SECONDS_TO_RECORD="${1:-30}"
BAG_NAME="${2:-atl4s-$(date -u +%Y%m%d-%H%M%S)}"
API="${ROSBAG_MANAGER_URL:-http://127.0.0.1:8086}"

if ! curl -fsS "${API}/healthz" > /dev/null 2>&1; then
    echo "[bag-record] rosbag-manager not reachable at ${API}; is the pipeline up?" >&2
    exit 1
fi

echo "[bag-record] recording for ${SECONDS_TO_RECORD}s as ${BAG_NAME}"
curl -fsS -X POST "${API}/api/record/start" \
    -H 'content-type: application/json' \
    -d "{\"name\":\"${BAG_NAME}\",\"duration\":${SECONDS_TO_RECORD}}" > /dev/null

sleep "${SECONDS_TO_RECORD}"

echo "[bag-record] waiting for upload to finish"
for _ in $(seq 1 60); do
    uploaded=$(curl -fsS "${API}/api/uploads" \
        | jq -r ".[] | select(.name == \"${BAG_NAME}\") | .uploaded" \
        || echo "")
    if [[ "$uploaded" == "true" ]]; then
        echo "[bag-record] uploaded: gs://${GCS_BUCKET:-atl4s-rosbags}/${BAG_NAME}/"
        exit 0
    fi
    sleep 2
done

echo "[bag-record] upload did not complete within 120s; check 'docker compose logs rosbag-manager'" >&2
exit 1
