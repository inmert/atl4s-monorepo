#!/usr/bin/env python3
"""Smoke-test the new DefectTracker end-to-end against a real iPad bag.

Skips the Poisson mesh path; only exercises:
  - for_each_frame_with_sinks() — depth/color/pose extraction
  - crackseg HTTP at $ARACHNID_CRACKSEG_URL (default 127.0.0.1:8092)
  - DefectTracker.on_frame() — projection + voxel hash + state machine
  - DefectTracker.flush() — v3 payload generation

Usage:
    python3 smoke_defect_tracker.py /tmp/probe-scan.bag [--max-frames 200]

Caps frame count by default (--max-frames 200) since crackseg is ~50ms per
frame on the L4 — 200 frames * stride 4 ≈ 800 source frames ≈ ~10s of bag
walltime, finishes in well under a minute. Override for full bag runs.

Prints the defects.json v3 payload at the end, plus per-defect summary.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

# Ensure mesh-worker is on sys.path when run from scripts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build_mesh import for_each_frame_with_sinks  # noqa: E402
from defects.state import DefectTracker                       # noqa: E402
from defects.crackseg_client import is_available, CRACKSEG_URL  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("smoke")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bag", help="path to scan.bag")
    ap.add_argument("--max-frames", type=int, default=200,
                    help="cap frames processed (default 200; pass 0 for full bag)")
    ap.add_argument("--stride", type=int, default=4,
                    help="frame stride into the bag (default 4)")
    ap.add_argument("--scan-id", default="smoke-test",
                    help="scan_id stamped into defect_id hashes")
    ap.add_argument("--out", default="/tmp/defects.json",
                    help="where to write the v3 payload (default /tmp/defects.json)")
    args = ap.parse_args()

    if not is_available():
        log.error("crackseg is not reachable at %s — aborting smoke test", CRACKSEG_URL)
        return 2
    log.info("crackseg OK at %s", CRACKSEG_URL)

    tracker = DefectTracker(scan_id=args.scan_id)

    t0 = time.time()
    for_each_frame_with_sinks(
        args.bag, [tracker],
        frame_stride=args.stride,
        max_frames=args.max_frames if args.max_frames > 0 else None,
    )
    elapsed = time.time() - t0

    payload = tracker.flush()
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    print()
    print("=" * 72)
    print(f"SMOKE RESULT · {elapsed:.1f}s wall · {tracker.frames_processed} frames")
    print(f"             · {tracker.frames_with_detections} frames had crack detections")
    print(f"             · grid voxels: {len(tracker.grid)}")
    print(f"             · confirmed defects: {len(payload['defects'])}")
    print("=" * 72)
    for i, d in enumerate(payload["defects"][:10]):
        print(
            f"  #{i+1}  id={d['defect_id']}  vol={d['volume_m3']*1e3:7.2f} L  "
            f"voxels={d['voxel_count']:4}  frames={d['frames_observed']:3}  "
            f"centroid=({d['centroid_world'][0]:+.2f},{d['centroid_world'][1]:+.2f},{d['centroid_world'][2]:+.2f})"
        )
    print(f"\nfull payload → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
