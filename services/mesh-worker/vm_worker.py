"""mesh-worker/vm_worker.py — Pub/Sub PULL subscriber for the VM.

The mesh-worker used to run on Cloud Run as a Flask push-handler. It
moved to the GPU VM (next to crackseg) so DefectTracker can call
http://127.0.0.1:8092/infer over loopback — without that, every
defect inference round-trips the public internet.

On the VM the entrypoint is no longer an HTTP server. We open a pull
subscription against the same Pub/Sub topic (mesh-build-requests),
process messages one at a time, and ack on success / nack on failure
for retry.

Health endpoint stays available on localhost:8080 so docker-compose's
healthcheck has something to poll.

Env (mirrors the Cloud Run defaults so existing tools work):
  GCP_PROJECT_ID        default arachnid-atlas
  PUBSUB_SUBSCRIPTION   default mesh-build-pull
  MAX_CONCURRENT        default 1 (mesh builds are GPU/CPU-heavy; serialize)
  ACK_DEADLINE_S        default 1800 (30 min — Pub/Sub max)
  HEALTH_PORT           default 8080
"""
from __future__ import annotations

import base64
import json
import logging
import os
import signal
import sys
import threading
import time
import traceback
from concurrent.futures import TimeoutError as FuturesTimeout
from http.server import BaseHTTPRequestHandler, HTTPServer

from google.cloud import pubsub_v1

from build_mesh import build_mesh_for_scan

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("mesh-worker.vm")

PROJECT_ID       = os.environ.get("GCP_PROJECT_ID", "arachnid-atlas")
SUBSCRIPTION     = os.environ.get("PUBSUB_SUBSCRIPTION", "mesh-build-pull")
MAX_CONCURRENT   = int(os.environ.get("MAX_CONCURRENT", "1"))
ACK_DEADLINE_S   = int(os.environ.get("ACK_DEADLINE_S", "1800"))
HEALTH_PORT      = int(os.environ.get("HEALTH_PORT", "8080"))

# ── Health endpoint ────────────────────────────────────────────────────────


_LAST_OK = {"ts": time.time(), "ack": 0, "nack": 0, "running": False}


class _Health(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return  # quiet — would spam every health probe otherwise

    def do_GET(self):
        if self.path != "/healthz":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({
            "ok": True,
            "subscription": SUBSCRIPTION,
            "last_activity_age_s": int(time.time() - _LAST_OK["ts"]),
            "ack_count": _LAST_OK["ack"],
            "nack_count": _LAST_OK["nack"],
            "currently_processing": _LAST_OK["running"],
        }).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_health_thread() -> None:
    def _run():
        try:
            srv = HTTPServer(("0.0.0.0", HEALTH_PORT), _Health)
            log.info("health endpoint listening on :%d", HEALTH_PORT)
            srv.serve_forever()
        except Exception:
            log.exception("health server died")

    t = threading.Thread(target=_run, name="health", daemon=True)
    t.start()


# ── Message handler ────────────────────────────────────────────────────────


def _handle(message: pubsub_v1.subscriber.message.Message) -> None:
    """One Pub/Sub message → one build_mesh_for_scan call.

    Pub/Sub PUSH delivery encoded data as base64 inside an envelope; PULL
    delivers the raw bytes directly on message.data. Either way the payload
    is the same JSON shape Vercel publishes:
      { "site_id": "...", "scan_id": "..." }
    """
    msg_id = message.message_id
    try:
        # PULL gives us raw bytes — no base64 wrapping. Some pipelines
        # double-encode anyway; handle both for safety.
        raw = message.data
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            # Maybe it's still base64'd (push-envelope leftover).
            payload = json.loads(base64.b64decode(raw).decode("utf-8"))
    except Exception as e:
        log.warning("message %s undecodable: %s — acking to drop", msg_id, e)
        message.ack()
        _LAST_OK["nack"] += 1
        return

    site_id = (payload.get("site_id") or "").strip()
    scan_id = (payload.get("scan_id") or "").strip()
    if not site_id or not scan_id:
        log.warning("message %s missing site/scan: %s — acking to drop", msg_id, payload)
        message.ack()
        _LAST_OK["nack"] += 1
        return

    log.info("dispatch msg=%s site=%s scan=%s", msg_id, site_id, scan_id)
    _LAST_OK["running"] = True
    t0 = time.time()
    try:
        result = build_mesh_for_scan(site_id, scan_id)
        log.info("build OK msg=%s · %.1fs · %s", msg_id, time.time() - t0, result)
        message.ack()
        _LAST_OK["ack"] += 1
    except RuntimeError as e:
        # Permanent failure (e.g. bag has no usable depth, missing pose
        # stream). Redelivery will hit the same wall — ACK so Pub/Sub
        # stops retrying. The S3 mesh-request.json sentinel survives as
        # a record of the dropped request; an operator can re-trigger
        # after the source bag is fixed.
        log.error("build PERMANENT-FAILURE msg=%s · %.1fs · %s — acking",
                  msg_id, time.time() - t0, e)
        message.ack()
        _LAST_OK["ack"] += 1   # treated as terminal, not as a retry win
    except Exception as e:
        # NACK → Pub/Sub redelivers with exponential backoff. Logged
        # stacktrace lands in journalctl on the VM. Reserved for
        # transient failures (network blips, GCS 5xx, OOM).
        log.error("build FAILED msg=%s · %.1fs · %s\n%s",
                  msg_id, time.time() - t0, e, traceback.format_exc())
        message.nack()
        _LAST_OK["nack"] += 1
    finally:
        _LAST_OK["running"] = False
        _LAST_OK["ts"] = time.time()


# ── Subscriber loop ────────────────────────────────────────────────────────


def main() -> int:
    _start_health_thread()

    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION)

    flow_control = pubsub_v1.types.FlowControl(
        max_messages=MAX_CONCURRENT,        # serialize: only one bag at a time
        max_lease_duration=ACK_DEADLINE_S,
    )

    log.info("subscribing to %s · max_concurrent=%d ack_deadline=%ds",
             sub_path, MAX_CONCURRENT, ACK_DEADLINE_S)
    future = subscriber.subscribe(sub_path, callback=_handle, flow_control=flow_control)

    # SIGTERM from docker stop → cancel cleanly, drain in-flight.
    def _shutdown(signum, frame):
        log.info("signal %d — cancelling subscription", signum)
        future.cancel()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)

    try:
        # Block forever until cancellation. The library handles retries +
        # ack-extensions for long-running messages internally.
        future.result()
    except FuturesTimeout:
        log.warning("subscription timed out — exiting for restart")
        return 1
    except KeyboardInterrupt:
        log.info("interrupted — bye")
        return 0
    except Exception:
        log.exception("subscription died — exiting for restart")
        return 1
    finally:
        subscriber.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
