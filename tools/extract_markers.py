"""Extract small green numbered markers from the marked board image."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "images" / "board-marked.jpg"
OUT = ROOT / "game" / "cells.json"
DBG = ROOT / "game" / "cells-debug.png"
MASK_DBG = ROOT / "game" / "markers-mask.png"


def main() -> None:
    bgr = cv2.imread(str(IMG))
    h, w = bgr.shape[:2]
    print("size", w, h)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # Small marker dots: saturated green with bright/white number
    # Sample a few expected regions near start
    for name, x, y in [("m1", 175, 155), ("m10", 480, 155), ("m50", 400, 580)]:
        if 0 <= x < w and 0 <= y < h:
            print(name, "bgr", bgr[y, x].tolist(), "hsv", hsv[y, x].tolist())

    # Broad green for markers (not the large green path cells which are teal-ish larger)
    green = cv2.inRange(hsv, (35, 60, 40), (95, 255, 220))
    # Also try darker green markers
    green2 = cv2.inRange(hsv, (40, 80, 30), (90, 255, 180))
    mask = cv2.bitwise_or(green, green2)

    # Exclude large green special cells by size later; open small noise
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    mask[0:40, :] = 0
    cv2.imwrite(str(MASK_DBG), mask)

    nlab, labels, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    markers = []
    for i in range(1, nlab):
        area = int(stats[i, cv2.CC_STAT_AREA])
        bw = int(stats[i, cv2.CC_STAT_WIDTH])
        bh = int(stats[i, cv2.CC_STAT_HEIGHT])
        # tiny markers only
        if area < 12 or area > 120:
            continue
        if bw < 4 or bh < 4 or bw > 18 or bh > 18:
            continue
        aspect = bw / max(bh, 1)
        if aspect < 0.55 or aspect > 1.8:
            continue
        cx, cy = float(cents[i][0]), float(cents[i][1])
        markers.append((cx, cy, area, bw, bh))

    print("raw markers", len(markers))

    # Dedup
    markers.sort(key=lambda m: -m[2])
    kept = []
    for m in markers:
        if any((m[0] - k[0]) ** 2 + (m[1] - k[1]) ** 2 < 8**2 for k in kept):
            continue
        kept.append(m)
    print("kept", len(kept))

    # If too few, try detecting bright green rings differently
    if len(kept) < 80:
        # Look for small bright blobs that are greenish
        # Difference of large orange path vs small overlays
        print("fallback: distance peaks on green mask")
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        dil = cv2.dilate(dist, np.ones((7, 7), np.uint8))
        peaks = (dist == dil) & (dist >= 2.0) & (dist <= 8.0)
        ys, xs = np.where(peaks)
        kept = []
        pts = list(zip(xs.tolist(), ys.tolist(), dist[ys, xs].tolist()))
        pts.sort(key=lambda t: -t[2])
        for x, y, r in pts:
            if any((x - kx) ** 2 + (y - ky) ** 2 < 8**2 for kx, ky, _ in kept):
                continue
            kept.append((float(x), float(y), float(r)))
        print("peak markers", len(kept))

    # Order path from start near Смоленск
    sx, sy = 0.17 * w, 0.215 * h
    start = min(kept, key=lambda c: (c[0] - sx) ** 2 + (c[1] - sy) ** 2)
    ordered = [start]
    rest = [c for c in kept if c is not start]
    while rest:
        last = ordered[-1]
        if len(ordered) >= 2:
            prev = ordered[-2]
            vx, vy = last[0] - prev[0], last[1] - prev[1]
            n = (vx * vx + vy * vy) ** 0.5 or 1
            vx, vy = vx / n, vy / n
        else:
            vx, vy = 1.0, 0.2

        by_dist = sorted(rest, key=lambda c: (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2)
        best, best_s = None, 1e18
        for c in by_dist[:12]:
            dx, dy = c[0] - last[0], c[1] - last[1]
            d = (dx * dx + dy * dy) ** 0.5
            align = 0 if d < 1 else (dx * vx + dy * vy) / d
            s = d - 10 * max(0, align)
            if d > 55:
                s += (d - 55) * 2
            if s < best_s:
                best_s, best = s, c
        ordered.append(best)
        rest.remove(best)

    ex, ey = 0.82 * w, 0.18 * h
    if (ordered[0][0] - ex) ** 2 + (ordered[0][1] - ey) ** 2 < (ordered[-1][0] - ex) ** 2 + (
        ordered[-1][1] - ey
    ) ** 2:
        ordered.reverse()

    # Trim/pad to 100
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
        ordered.insert(longest_i + 1, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0))

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

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    dr = ImageDraw.Draw(im)
    for a, b in zip(cells, cells[1:]):
        dr.line((a["x"] / 100 * w, a["y"] / 100 * h, b["x"] / 100 * w, b["y"] / 100 * h), fill=(0, 255, 255), width=1)
    for c in cells:
        px, py = c["x"] / 100 * w, c["y"] / 100 * h
        dr.ellipse((px - 5, py - 5, px + 5, py + 5), outline=(255, 0, 255), width=2)
        if c["n"] % 5 == 0 or c["n"] <= 3:
            dr.text((px + 6, py - 6), str(c["n"]), fill=(255, 255, 0))
    im.save(DBG)
    jumps = [
        (((a["x"] - b["x"]) * w / 100) ** 2 + ((a["y"] - b["y"]) * h / 100) ** 2) ** 0.5
        for a, b in zip(cells, cells[1:])
    ]
    print("count", len(cells), "mean/max jump", round(sum(jumps) / len(jumps), 1), round(max(jumps), 1))
    print("big", [(i + 1, round(j, 1)) for i, j in enumerate(jumps) if j > 40][:20])


if __name__ == "__main__":
    main()
