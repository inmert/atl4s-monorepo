#!/usr/bin/env bash
# One-shot host setup for the console: build the UI, create a Python venv, and
# install backend deps. Re-runnable (idempotent).
set -euo pipefail

CONSOLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$CONSOLE_DIR"

echo "[1/3] Building UI…"
"$CONSOLE_DIR/scripts/build-ui.sh"

echo "[2/3] Creating Python venv (.venv)…"
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi

echo "[3/3] Installing backend deps…"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

echo
echo "Done. Run in the foreground:   console/scripts/run.sh"
echo "Or install as a service:       console/scripts/install-service.sh"
