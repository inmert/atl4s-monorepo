#!/usr/bin/env bash
# Run the console backend in the foreground (dev). The systemd service uses the
# same venv + entrypoint; see install-service.sh.
set -euo pipefail

CONSOLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$CONSOLE_DIR/.." && pwd)"
cd "$CONSOLE_DIR"

# Export only the keys the console needs from the repo .env. We avoid
# `source .env` because some values (e.g. RECORD_TOPICS) contain spaces and
# would be misparsed by the shell.
if [ -f "$REPO_DIR/.env" ]; then
    for key in BAG_WEB_USER BAG_WEB_PASS CONSOLE_BIND CONSOLE_PORT; do
        val="$(grep -E "^${key}=" "$REPO_DIR/.env" | tail -1 | cut -d= -f2- || true)"
        [ -n "$val" ] && export "$key=$val"
    done
fi

exec .venv/bin/uvicorn api.main:app \
    --host "${CONSOLE_BIND:-0.0.0.0}" \
    --port "${CONSOLE_PORT:-8089}"
