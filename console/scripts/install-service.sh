#!/usr/bin/env bash
# Install + start the console as a systemd service (atl4s-console.service).
# Run console/scripts/setup.sh first (needs the .venv + built UI).
set -euo pipefail

CONSOLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$CONSOLE_DIR/.." && pwd)"
RUN_USER="$(id -un)"
UNIT_NAME=atl4s-console.service
DEST="/etc/systemd/system/$UNIT_NAME"

if [ ! -x "$CONSOLE_DIR/.venv/bin/uvicorn" ]; then
    echo "error: $CONSOLE_DIR/.venv not found — run console/scripts/setup.sh first." >&2
    exit 1
fi

echo "Installing $UNIT_NAME (User=$RUN_USER, WorkingDirectory=$CONSOLE_DIR)…"
sed -e "s#@USER@#$RUN_USER#g" \
    -e "s#@CONSOLE_DIR@#$CONSOLE_DIR#g" \
    -e "s#@REPO_DIR@#$REPO_DIR#g" \
    "$CONSOLE_DIR/deploy/$UNIT_NAME.template" | sudo tee "$DEST" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now "$UNIT_NAME"
sleep 1
sudo systemctl --no-pager --full status "$UNIT_NAME" | head -14

echo
echo "Logs:    journalctl -u $UNIT_NAME -f"
echo "Restart: sudo systemctl restart $UNIT_NAME"
