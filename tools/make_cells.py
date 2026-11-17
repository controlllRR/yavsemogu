"""Detect real cells (high mask fill ratio) and order with strict local jumps."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "images" / "board-map.jpg"
OUT = ROOT / "game" / "cells.json"
DBG = ROOT / "game" / "cells-debug.png"


def main() -> None:
    bgr = cv2.imread(str(IMG))
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    mask = cv2.inRange(hsv, (4, 75, 95), (30, 255, 255))
    mask = cv2.bitwise_or(mask, cv2.inRange(hsv, (35, 45, 65), (100, 255, 255)))
    mask = cv2.bitwise_or(mask, cv2.inRange(hsv, (112, 35, 50), (168, 255, 255)))
    mask[0:48, :] = 0

    # Connected components of right size = cells
    m = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2)))
    nlab, labels, stats, cents = cv2.connectedComponentsWithStats(m, 8)
    comps = []
    for i in range(1, nlab):
        area = stats[i, cv2.CC_STAT_AREA]
        bw = stats[i, cv2.CC_STAT_WIDTH]
        bh = stats[i, cv2.CC_STAT_HEIGHT]
        if area < 70 or area > 550:
            continue
        if bw < 11 or bh < 11 or bw > 36 or bh > 36:
            continue
        aspect = bw / max(bh, 1)
        if not (0.65 <= aspect <= 1.55):
            continue
        # circularity
        comp = (labels == i).astype(np.uint8) * 255
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        peri = cv2.arcLength(cnts[0], True)
        circ = 4 * np.pi * area / (peri * peri + 1e-6)
        if circ < 0.62:
            continue
        cx, cy = float(cents[i][0]), float(cents[i][1])
        comps.append((cx, cy, (bw + bh) / 4))

    print("components", len(comps))

    # Also hough on mask for missed ones
    blur = cv2.GaussianBlur(m, (5, 5), 0)
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1.1, 15, param1=80, param2=8, minRadius=7, maxRadius=15)
    if circles is not None:
        for x, y, r in np.round(circles[0]).astype(int):
            # fill ratio inside circle
            yy, xx = np.ogrid[-r : r + 1, -r : r + 1]
            disk = xx * xx + yy * yy <= r * r
            y0, x0 = y - r, x - r
            y1, x1 = y + r + 1, x + r + 1
            if y0 < 0 or x0 < 0 or y1 > h or x1 > w:
                continue
            patch = m[y0:y1, x0:x1]
            if patch.shape[:2] != disk.shape:
                continue
            ratio = patch[disk].mean() / 255.0
            if ratio < 0.45:
                continue
            comps.append((float(x), float(y), float(r)))

    # Dedup
    comps.sort(key=lambda c: -c[2])
    kept = []
    for c in comps:
        if any((c[0] - k[0]) ** 2 + (c[1] - k[1]) ** 2 < 12**2 for k in kept):
            continue
        kept.append(c)
    print("kept", len(kept))

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    dr = ImageDraw.Draw(im)
    for c in kept:
        dr.ellipse((c[0] - 4, c[1] - 4, c[0] + 4, c[1] + 4), outline="#00ff88", width=2)
    im.save(ROOT / "game" / "peaks-debug.png")

    # Strict chain: only jump to nearest within 48px; if stuck, increase radius gradually
    sx, sy = 0.168 * w, 0.218 * h
    start = min(kept, key=lambda c: (c[0] - sx) ** 2 + (c[1] - sy) ** 2)
    ordered = [start]
    rest = set(range(len(kept)))
    rest.remove(kept.index(start)) if start in kept else None
    # rebuild with indices
    pts = kept[:]
    start_i = min(range(len(pts)), key=lambda i: (pts[i][0] - sx) ** 2 + (pts[i][1] - sy) ** 2)
    ordered_i = [start_i]
    unused = set(range(len(pts))) - {start_i}

    while unused:
        last = pts[ordered_i[-1]]
        if len(ordered_i) >= 2:
            prev = pts[ordered_i[-2]]
            vx, vy = last[0] - prev[0], last[1] - prev[1]
            n = (vx * vx + vy * vy) ** 0.5 or 1
            vx, vy = vx / n, vy / n
        else:
            vx, vy = 1.0, 0.2

        best = None
        for radius in (42, 55, 70, 95, 140, 9999):
            cand = []
            for i in unused:
                c = pts[i]
                dx, dy = c[0] - last[0], c[1] - last[1]
                d = (dx * dx + dy * dy) ** 0.5
                if d > radius:
                    continue
                align = 0 if d < 1 else (dx * vx + dy * vy) / d
                cand.append((d - 15 * max(0, align), i, d))
            if cand:
                cand.sort()
                best = cand[0][1]
                break
        ordered_i.append(best)
        unused.remove(best)

    ordered = [pts[i] for i in ordered_i]
    ex, ey = 0.785 * w, 0.185 * h
    if (ordered[0][0] - ex) ** 2 + (ordered[0][1] - ey) ** 2 < (ordered[-1][0] - ex) ** 2 + (
        ordered[-1][1] - ey
    ) ** 2:
        ordered.reverse()

    # Select exactly 100: if more, drop points with smallest removal-cost until 100
    # Prefer keeping points that are real path - drop ones that create zigzags
    while len(ordered) > 100:
        worst_i, worst_gain = 1, -1e9
        for i in range(1, len(ordered) - 1):
            a, b, c = ordered[i - 1], ordered[i], ordered[i + 1]
            gain = (
                ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
                + ((b[0] - c[0]) ** 2 + (b[1] - c[1]) ** 2) ** 0.5
                - ((a[0] - c[0]) ** 2 + (a[1] - c[1]) ** 2) ** 0.5
            )
            if gain > worst_gain:
                worst_gain, worst_i = gain, i
        ordered.pop(worst_i)

    while len(ordered) < 100:
        longest_i, longest_d = 0, -1.0
        for i in range(len(ordered) - 1):
            a, b = ordered[i], ordered[i + 1]
            d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            if d > longest_d:
                longest_d, longest_i = d, i
        a, b = ordered[longest_i], ordered[longest_i + 1]
        ordered.insert(longest_i + 1, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 10))

    specials = {
        12: "green",
        28: "green",
        49: "green",
        70: "green",
        83: "green",
        8: "purple",
        17: "purple",
        41: "purple",
        60: "purple",
        78: "purple",
        90: "purple",
    }
    cells = [
        {
            "n": i,
            "x": round(100 * c[0] / w, 3),
            "y": round(100 * c[1] / h, 3),
            "kind": specials.get(i, "orange"),
        }
        for i, c in enumerate(ordered, 1)
    ]
    OUT.write_text(json.dumps({"width": w, "height": h, "cells": cells}, ensure_ascii=False, indent=2), encoding="utf-8")

    im2 = Image.fromarray(rgb)
    dr2 = ImageDraw.Draw(im2)
    for a, b in zip(cells, cells[1:]):
        dr2.line((a["x"] / 100 * w, a["y"] / 100 * h, b["x"] / 100 * w, b["y"] / 100 * h), fill=(255, 255, 255), width=1)
    for c in cells:
        px, py = c["x"] / 100 * w, c["y"] / 100 * h
        col = {"orange": "#ff9800", "green": "#22c55e", "purple": "#c084fc"}[c["kind"]]
        dr2.ellipse((px - 5, py - 5, px + 5, py + 5), outline=col, width=2)
        dr2.text((px - 4, py - 14), str(c["n"]), fill="white")
    im2.save(DBG)
    jumps = [
        (((a["x"] - b["x"]) * w / 100) ** 2 + ((a["y"] - b["y"]) * h / 100) ** 2) ** 0.5
        for a, b in zip(cells, cells[1:])
    ]
    print("count", len(cells), "mean/max", round(sum(jumps) / len(jumps), 1), round(max(jumps), 1))
    print("big", [(i + 1, round(j, 1)) for i, j in enumerate(jumps) if j > 45])


if __name__ == "__main__":
    main()
