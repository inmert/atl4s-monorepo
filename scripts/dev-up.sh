#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose --profile sim up -d
docker compose ps
