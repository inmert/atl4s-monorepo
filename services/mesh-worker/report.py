"""mesh-worker/report.py — operator-deliverable PDF generation.

Replaces the legacy flight-ui-static/scripts/build-scan-report.mjs (Node +
Playwright). Runs inline at the end of build_mesh_for_scan() once the
mesh, defect bundle, splat.png, and path.png are all on disk, and pushes
report.pdf to S3 alongside everything else.

Layout matches the original 4-panel template:

    +----------------------------------------+
    |  Scan Report                           |  H1 with orange rule
    +-----------------------+----------------+
    | GPS coordinate        | Total volume   |  header strip (2 cols)
    +-----------------------+----------------+
    | 3/4 view  (splat.png) | Map + route    |
    +-----------------------+----------------+
    | Scan area  SLAM stats | Defects table  |
    +-----------------------+----------------+
    | ARACHNID · site · scanId       v3      |  footer
    +----------------------------------------+

Uses reportlab — pure pip, no system libs beyond what Python+open3d already
pull in. The layout is built with Platypus tables; styles match the JS
template's design tokens (orange #d9461a accent, Letter @ 0.5 in margins,
SF Pro / monospace mix).
"""
from __future__ import annotations

import io
import json
import logging
import os
from typing import Optional

import numpy as np

log = logging.getLogger("mesh-worker.report")


# ── Design tokens (mirror docs/MOBILE_SHELL.md + the JS template) ─────
FG        = (0.086, 0.098, 0.114)   # #16191d
MUTED     = (0.365, 0.392, 0.427)   # #5d646d
RULE      = (0.847, 0.867, 0.886)   # #d8dde2
HI        = (0.851, 0.275, 0.102)   # #d9461a — orange accent
PANEL_BG  = (0.980, 0.984, 0.988)   # #fafbfc


def _format_volume(m3: float) -> str:
    """Largest-unit-that-fits volume formatter (m³ → L → mL)."""
    if m3 >= 1.0:    return f"{m3:.2f} m³"
    if m3 >= 1e-3:   return f"{m3 * 1e3:.2f} L"
    return f"{m3 * 1e6:.0f} mL"


def build_report(
    site_id: str,
    scan_id: str,
    defects_payload: dict,
    splat_png_path: Optional[str],
    path_png_path: Optional[str],
    slam_stats: dict,
    out_path: str,
) -> Optional[str]:
    """Render the operator PDF. Returns out_path on success, None on failure.

    `slam_stats` is the SLAM/bag metadata block built by build_mesh.py
    (captured at, duration, bag size, frames, pose frames, path length,
    world bbox, volume_m3).
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            Image as RLImage, KeepInFrame,
        )
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    except ImportError as e:
        log.warning("reportlab not installed (%s) — report.pdf skipped", e)
        return None

    PAGE_W, PAGE_H = letter
    MARGIN_L = MARGIN_R = 0.5 * inch
    MARGIN_T = 0.55 * inch
    MARGIN_B = 0.65 * inch
    CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

    doc = SimpleDocTemplate(
        out_path,
        pagesize=letter,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title=f"ARACHNID Scan Report — {scan_id}",
    )
    styles = getSampleStyleSheet()

    # ── Reusable text styles ─────────────────────────────────────────
    h1_style = ParagraphStyle(
        "h1", parent=styles["Heading1"],
        fontName="Helvetica", fontSize=24, leading=28,
        textColor=colors.Color(*FG), spaceAfter=6,
        borderColor=colors.Color(*HI), borderWidth=1.4,
        borderPadding=(0, 0, 6, 0),
    )
    label_style = ParagraphStyle(
        "label", parent=styles["BodyText"],
        fontName="Helvetica-Bold", fontSize=8.5, leading=10,
        textColor=colors.Color(*MUTED), letterSpacing=0.14,
        spaceAfter=3,
    )
    val_style = ParagraphStyle(
        "val", parent=styles["BodyText"],
        fontName="Courier", fontSize=13, leading=16,
        textColor=colors.Color(*FG),
    )
    sub_style = ParagraphStyle(
        "sub", parent=styles["BodyText"],
        fontName="Helvetica", fontSize=8, leading=10,
        textColor=colors.Color(*MUTED), spaceBefore=3,
    )
    quad_title_style = ParagraphStyle(
        "quad_title", parent=styles["BodyText"],
        fontName="Helvetica-Bold", fontSize=9, leading=11,
        textColor=colors.Color(*HI), letterSpacing=0.16,
    )
    quad_sub_style = ParagraphStyle(
        "quad_sub", parent=styles["BodyText"],
        fontName="Helvetica", fontSize=8.5, leading=10,
        textColor=colors.Color(*MUTED), alignment=TA_RIGHT,
    )
    kv_k_style = ParagraphStyle(
        "kv_k", parent=styles["BodyText"],
        fontName="Helvetica", fontSize=8, leading=11,
        textColor=colors.Color(*MUTED), letterSpacing=0.10,
    )
    kv_v_style = ParagraphStyle(
        "kv_v", parent=styles["BodyText"],
        fontName="Courier-Bold", fontSize=9, leading=11,
        textColor=colors.Color(*FG), alignment=TA_RIGHT,
    )
    defect_num_style = ParagraphStyle(
        "defect_num", parent=styles["BodyText"],
        fontName="Courier-Bold", fontSize=11, leading=13,
        textColor=colors.Color(*HI),
    )
    defect_type_style = ParagraphStyle(
        "defect_type", parent=styles["BodyText"],
        fontName="Helvetica-Bold", fontSize=9, leading=11,
        textColor=colors.Color(*FG),
    )
    defect_meta_style = ParagraphStyle(
        "defect_meta", parent=styles["BodyText"],
        fontName="Courier", fontSize=7.5, leading=9,
        textColor=colors.Color(*MUTED), spaceBefore=1,
    )

    story = []

    # ── H1 ───────────────────────────────────────────────────────────
    story.append(Paragraph("Scan Report", h1_style))
    story.append(Spacer(1, 10))

    # ── Header strip: GPS | Total Volume ─────────────────────────────
    vol_m3 = float(slam_stats.get("volume_m3") or 0)
    bbox_size = slam_stats.get("bbox_size") or ["—", "—", "—"]
    frames = slam_stats.get("frame_count", 0)
    gps_cell = [
        Paragraph("GPS COORDINATE", label_style),
        Paragraph("—  <font name='Helvetica' size=10 color='#5d646d'>latitude / longitude</font>", val_style),
        Paragraph("iPad scanner doesn't capture GPS yet — populate from CoreLocation in a future build", sub_style),
    ]
    vol_cell = [
        Paragraph("TOTAL VOLUME", label_style),
        Paragraph(f"{vol_m3:.2f} <font name='Helvetica' size=10 color='#5d646d'>m³</font>", val_style),
        Paragraph(f"world bbox {bbox_size[0]} × {bbox_size[1]} × {bbox_size[2]} m · {frames} frames", sub_style),
    ]
    hdr = Table(
        [[gps_cell, vol_cell]],
        colWidths=[CONTENT_W / 2 - 6, CONTENT_W / 2 - 6],
        hAlign="LEFT",
    )
    hdr.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), colors.Color(*PANEL_BG)),
        ("BOX",         (0, 0), (-1, -1), 0.6, colors.Color(*RULE)),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",(0, 0), (-1, -1), 12),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 12))

    # ── Quadrant builders ────────────────────────────────────────────
    QUAD_H = 200   # 200pt body each
    HEAD_H = 24

    def _image_panel(img_path, title, sub):
        head = Table(
            [[Paragraph(title, quad_title_style), Paragraph(sub, quad_sub_style)]],
            colWidths=[(CONTENT_W / 2 - 6) * 0.55, (CONTENT_W / 2 - 6) * 0.45],
        )
        head.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",(0, 0), (-1, -1), 12),
            ("TOPPADDING",  (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("LINEBELOW",   (0, 0), (-1, -1), 0.6, colors.Color(*RULE)),
        ]))
        body = None
        if img_path and os.path.isfile(img_path) and os.path.getsize(img_path) > 1024:
            try:
                body = RLImage(img_path, width=CONTENT_W / 2 - 18, height=QUAD_H - 4)
            except Exception as e:
                log.warning("image load failed for %s: %s", img_path, e)
        if body is None:
            body = Paragraph(
                f"<font name='Helvetica' size=9 color='#5d646d'>{title} pending</font>",
                styles["BodyText"],
            )
        return [head, Spacer(1, 4), body]

    # SLAM stats key-value rows
    def _slam_panel():
        head = Table(
            [[Paragraph("SCAN AREA", quad_title_style),
              Paragraph("SLAM stats", quad_sub_style)]],
            colWidths=[(CONTENT_W / 2 - 6) * 0.55, (CONTENT_W / 2 - 6) * 0.45],
        )
        head.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",(0, 0), (-1, -1), 12),
            ("TOPPADDING",  (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("LINEBELOW",   (0, 0), (-1, -1), 0.6, colors.Color(*RULE)),
        ]))
        rows = [
            ("Site",          str(site_id)),
            ("Captured",      slam_stats.get("captured_at", "—")),
            ("Duration",      f"{slam_stats.get('duration_s', '—')} s"),
            ("Bag size",      f"{slam_stats.get('bag_size_mb', '—')} MB"),
            ("Frames",        str(slam_stats.get("frame_count", 0))),
            ("Pose frames",   str(slam_stats.get("pose_count", 0))),
            ("Path length",   f"{slam_stats.get('walked_m', '—')} m"),
            ("World bbox X",  f"{(slam_stats.get('bbox_min') or ['—','—','—'])[0]} … {(slam_stats.get('bbox_max') or ['—','—','—'])[0]} m"),
            ("World bbox Y",  f"{(slam_stats.get('bbox_min') or ['—','—','—'])[1]} … {(slam_stats.get('bbox_max') or ['—','—','—'])[1]} m"),
            ("World bbox Z",  f"{(slam_stats.get('bbox_min') or ['—','—','—'])[2]} … {(slam_stats.get('bbox_max') or ['—','—','—'])[2]} m"),
            ("Volume (bbox)", f"{vol_m3:.2f} m³"),
        ]
        kv = Table(
            [[Paragraph(k.upper(), kv_k_style), Paragraph(v, kv_v_style)] for k, v in rows],
            colWidths=[(CONTENT_W / 2 - 18) * 0.55, (CONTENT_W / 2 - 18) * 0.45],
            hAlign="LEFT",
        )
        kv.setStyle(TableStyle([
            ("LINEBELOW",   (0, 0), (-1, -2), 0.4, colors.Color(*RULE)),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 0),
            ("TOPPADDING",  (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ]))
        return [head, Spacer(1, 4), kv]

    def _defects_panel():
        all_defects = defects_payload.get("defects", []) or []
        total = len(all_defects)
        top = all_defects[:10]
        sub = f"{total} confirmed · top {len(top)} shown" if total else "— no defects found"

        head = Table(
            [[Paragraph("DEFECTS", quad_title_style),
              Paragraph(sub, quad_sub_style)]],
            colWidths=[(CONTENT_W / 2 - 6) * 0.5, (CONTENT_W / 2 - 6) * 0.5],
        )
        head.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",(0, 0), (-1, -1), 12),
            ("TOPPADDING",  (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("LINEBELOW",   (0, 0), (-1, -1), 0.6, colors.Color(*RULE)),
        ]))
        if not top:
            empty = Paragraph(
                f"<font name='Helvetica' size=8 color='#5d646d'>"
                f"{defects_payload.get('frames_processed', 0)} frames scanned · "
                f"{defects_payload.get('dropped_low_voxels', 0) + defects_payload.get('dropped_low_hits', 0)} "
                f"low-confidence candidates filtered</font>",
                styles["BodyText"],
            )
            return [head, Spacer(1, 12), empty]

        rows = []
        for i, d in enumerate(top, 1):
            c = d.get("centroid_world") or [0, 0, 0]
            id_short = (d.get("defect_id") or "—")[:8]
            num   = Paragraph(f"{i:02d}", defect_num_style)
            label_p = Paragraph(
                f"{id_short} · {_format_volume(float(d.get('volume_m3', 0)))}<br/>"
                f"<font name='Courier' size=7.5 color='#5d646d'>"
                f"{d.get('voxel_count', 0)} vox · {d.get('total_hits', d.get('frames_observed', 0))} hits "
                f"· world ({c[0]:+.2f}, {c[1]:+.2f}, {c[2]:+.2f})</font>",
                defect_type_style,
            )
            rows.append([num, label_p])

        tbl = Table(
            rows,
            colWidths=[28, (CONTENT_W / 2 - 18) - 32],
            hAlign="LEFT",
        )
        tbl.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",(0, 0), (-1, -1), 8),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("BOX",         (0, 0), (-1, -1), 0.4, colors.Color(*RULE)),
            ("LINEBELOW",   (0, 0), (-1, -2), 0.4, colors.Color(*RULE)),
        ]))
        return [head, Spacer(1, 4), tbl]

    splat_panel = _image_panel(
        splat_png_path, "3/4 VIEW · SPLAT", f"last frame · {frames} accumulated",
    )
    path_panel = _image_panel(
        path_png_path, "MAP + ROUTE", f"walked {slam_stats.get('walked_m', '—')} m",
    )
    slam_panel = _slam_panel()
    defects_panel = _defects_panel()

    # Wrap each panel in a single-cell sub-table so we can border + size it.
    def _quad_wrap(content_list):
        inner = Table([[content_list]], colWidths=[CONTENT_W / 2 - 6])
        inner.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, -1), colors.Color(*PANEL_BG)),
            ("BOX",         (0, 0), (-1, -1), 0.6, colors.Color(*RULE)),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 0),
            ("TOPPADDING",  (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ]))
        return inner

    # 2x2 grid via outer Table — KeepInFrame keeps each panel from
    # spilling its own column even if a label runs long.
    grid = Table(
        [
            [KeepInFrame(CONTENT_W / 2 - 6, QUAD_H + HEAD_H + 8, [_quad_wrap(splat_panel)], hAlign="LEFT", vAlign="TOP", mode="shrink"),
             KeepInFrame(CONTENT_W / 2 - 6, QUAD_H + HEAD_H + 8, [_quad_wrap(path_panel)],  hAlign="LEFT", vAlign="TOP", mode="shrink")],
            [KeepInFrame(CONTENT_W / 2 - 6, 220, [_quad_wrap(slam_panel)],    hAlign="LEFT", vAlign="TOP", mode="shrink"),
             KeepInFrame(CONTENT_W / 2 - 6, 220, [_quad_wrap(defects_panel)], hAlign="LEFT", vAlign="TOP", mode="shrink")],
        ],
        colWidths=[CONTENT_W / 2 - 6, CONTENT_W / 2 - 6],
        rowHeights=[QUAD_H + HEAD_H + 8, 220],
        hAlign="LEFT",
    )
    grid.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 12),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(grid)

    # ── Footer ───────────────────────────────────────────────────────
    foot_style = ParagraphStyle(
        "foot", parent=styles["BodyText"],
        fontName="Helvetica", fontSize=8, leading=10,
        textColor=colors.Color(*MUTED),
    )
    foot_tag_style = ParagraphStyle(
        "foot_tag", parent=styles["BodyText"],
        fontName="Helvetica-Bold", fontSize=7, leading=9,
        textColor=colors.Color(0.769, 0.482, 0.086),  # #c47b16
        alignment=TA_RIGHT, letterSpacing=0.10,
    )
    story.append(Spacer(1, 6))
    footer = Table(
        [[
            Paragraph(
                f"ARACHNID · {site_id} · {scan_id}", foot_style,
            ),
            Paragraph("V3 PIPELINE", foot_tag_style),
        ]],
        colWidths=[CONTENT_W * 0.75, CONTENT_W * 0.25],
    )
    footer.setStyle(TableStyle([
        ("LINEABOVE",   (0, 0), (-1, -1), 0.6, colors.Color(*RULE)),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(footer)

    try:
        doc.build(story)
        sz = os.path.getsize(out_path)
        log.info("report.pdf built · %.1f KB", sz / 1024)
        return out_path
    except Exception as e:
        log.exception("doc.build failed: %s", e)
        return None
