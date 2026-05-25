#!/bin/bash
set -e
cd "$(dirname "$0")/.."
docker compose --profile sim up -d
docker compose ps
