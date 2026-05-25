#!/bin/bash
# List bags currently in the GCS bucket.
set -euo pipefail

BUCKET="${GCS_BUCKET:-atl4s-rosbags}"
gcloud storage ls -l "gs://${BUCKET}/**"
