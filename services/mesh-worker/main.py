"""mesh-worker/main.py — Cloud Run entrypoint.

Receives Pub/Sub push notifications from the `mesh-build-requests`
topic and dispatches each to `build_mesh.build_mesh_for_scan`.

Pub/Sub push envelope (gen2, after JSON decode):
  {
    "message": {
      "data": "<base64-encoded JSON payload>",
      "messageId": "...",
      "publishTime": "...",
      "attributes": {...}
    },
    "subscription": "projects/.../subscriptions/mesh-build-push"
  }

The encoded JSON payload (what Vercel publishes) is:
  { "site_id": "orin-drone", "scan_id": "pyramid-tight-..." }

Response semantics:
  2xx → Pub/Sub acks (stops retrying)
  4xx → bad-request; acks too (don't retry malformed messages)
  5xx → nack; Pub/Sub retries with exponential backoff
"""
from __future__ import annotations
import base64
import json
import logging
import os
import traceback
from flask import Flask, jsonify, request

from build_mesh import build_mesh_for_scan

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("mesh-worker")

app = Flask(__name__)


@app.get("/healthz")
def healthz():
    return ("ok", 200)


@app.post("/")
def handle_push():
    envelope = request.get_json(silent=True) or {}
    message = envelope.get("message") or {}
    raw = message.get("data")
    if not raw:
        log.warning("missing message.data; envelope=%s", envelope)
        return ("bad request: missing message.data", 400)

    try:
        payload = json.loads(base64.b64decode(raw).decode("utf-8"))
    except Exception as e:
        log.warning("decode failed: %s", e)
        return (f"bad request: decode failed: {e}", 400)

    site_id = (payload.get("site_id") or "").strip()
    scan_id = (payload.get("scan_id") or "").strip()
    if not site_id or not scan_id:
        log.warning("missing site_id/scan_id; payload=%s", payload)
        return ("bad request: missing site_id/scan_id", 400)

    log.info("dispatch site=%s scan=%s msg=%s",
             site_id, scan_id, message.get("messageId"))

    try:
        result = build_mesh_for_scan(site_id, scan_id)
    except Exception as e:
        # 5xx → Pub/Sub will redeliver. Logged stacktrace lands in
        # Cloud Logging under the mesh-worker service.
        log.error("mesh build failed: %s\n%s", e, traceback.format_exc())
        return (f"mesh build failed: {e}", 500)

    return jsonify({"ok": True, **result}), 200


if __name__ == "__main__":
    # Local-dev shim only — production uses gunicorn (see Dockerfile CMD).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
