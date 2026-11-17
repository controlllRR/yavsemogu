"""Keep only path-like circle clusters, order with short jumps, export cells."""
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


def detect(bgr):
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (5, 90, 120), (28, 255, 255))
    mask = cv2.bitwise_or(mask, cv2.inRange(hsv, (40, 55, 80), (95, 255, 230)))
    mask = cv2.bitwise_or(mask, cv2.inRange(hsv, (115, 40, 70), (160, 255, 220)))
    mask[0:48, :] = 0
    # carve big illustrations (percent boxes)
    for xp, yp, wp, hp in [
        (8, 5, 18, 16),   # смоленск building (keep path below)
        (42, 0, 14, 12),  # fountain
        (22, 18, 14, 14), # kids
        (18, 32, 12, 14), # deer
        (45, 30, 14, 16), # carousel
        (8, 58, 12, 28),  # tower
        (38, 68, 16, 16), # samovar
        (72, 55, 16, 22), # church
        (80, 30, 16, 18), # firebird
        (72, 5, 20, 14),  # house (keep path near)
        (30, 2, 28, 8),   # title
    ]:
        x, y = int(xp / 100 * w), int(yp / 100 * h)
        bw, bh = int(wp / 100 * w), int(hp / 100 * h)
        # don't carve too aggressively on path zones — skip carving
        pass

    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    blur = cv2.GaussianBlur(mask, (5, 5), 0)
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1.1, 13, param1=65, param2=11, minRadius=8, maxRadius=14)
    pts = []
    if circles is None:
        return pts, mask
    for x, y, r in np.round(circles[0]).astype(int):
        if not (20 < x < w - 20 and 52 < y < h - 12):
            continue
        # ring must be path-colored
        ok = 0
        bright = 0
        for ang in range(0, 360, 30):
            px = int(x + r * 0.6 * np.cos(np.deg2rad(ang)))
            py = int(y + r * 0.6 * np.sin(np.deg2rad(ang)))
            if 0 <= px < w and 0 <= py < h:
                if mask[py, px] > 0:
                    ok += 1
                bright += int(bgr[py, px].sum())
        if ok < 6:
            continue
        # center should be darker-ish (digit) — not mandatory for green/purple
        pts.append((float(x), float(y)))
    # dedup
    kept = []
    for p in sorted(pts, key=lambda t: (t[1], t[0])):
        if any((p[0] - k[0]) ** 2 + (p[1] - k[1]) ** 2 < 11**2 for k in kept):
            continue
        kept.append(p)
    return kept, mask


def filter_neighbors(pts, max_nn=48, min_neighbors=1):
    out = []
    for i, p in enumerate(pts):
        n = 0
        for j, q in enumerate(pts):
            if i == j:
                continue
            if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 < max_nn**2:
                n += 1
        if n >= min_neighbors:
            out.append(p)
    return out


def order_path(pts, start, end):
    start_p = min(pts, key=lambda p: (p[0] - start[0]) ** 2 + (p[1] - start[1]) ** 2)
    ordered = [start_p]
    rest = [p for p in pts if p is not start_p]
    while rest:
        last = ordered[-1]
        if len(ordered) >= 2:
            prev = ordered[-2]
            vx, vy = last[0] - prev[0], last[1] - prev[1]
            n = (vx * vx + vy * vy) ** 0.5 or 1
            vx, vy = vx / n, vy / n
        else:
            vx, vy = 1, 0.2
        scored = []
        for p in rest:
            dx, dy = p[0] - last[0], p[1] - last[1]
            d = (dx * dx + dy * dy) ** 0.5
            align = 0 if d < 1 else (dx * vx + dy * vy) / d
            scored.append((d - 12 * max(0, align) + (0 if d < 45 else (d - 45) * 4), p, d))
        scored.sort(key=lambda t: t[0])
        # prefer among close
        close = [t for t in scored if t[2] <= 50]
        pick = (close or scored)[0][1]
        ordered.append(pick)
        rest.remove(pick)

    # orient
    if (ordered[0][0] - end[0]) ** 2 + (ordered[0][1] - end[1]) ** 2 < (
        ordered[-1][0] - end[0]
    ) ** 2 + (ordered[-1][1] - end[1]) ** 2:
        ordered.reverse()
    return ordered


def main():
    bgr = cv2.imread(str(IMG))
    h, w = bgr.shape[:2]
    pts, mask = detect(bgr)
    print("raw", len(pts))
    pts = filter_neighbors(pts, 55, 1)
    print("filtered", len(pts))

    start = (0.168 * w, 0.218 * h)
    end = (0.89 * w, 0.155 * h)
    ordered = order_path(pts, start, end)

    # trim/pad to 100
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
        li, ld = 0, -1
        for i in range(len(ordered) - 1):
            a, b = ordered[i], ordered[i + 1]
            d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            if d > ld:
                ld, li = d, i
        a, b = ordered[li], ordered[li + 1]
        ordered.insert(li + 1, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))

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
        {"n": i, "x": round(100 * p[0] / w, 3), "y": round(100 * p[1] / h, 3), "kind": specials.get(i, "orange")}
        for i, p in enumerate(ordered, 1)
    ]
    OUT.write_text(json.dumps({"width": w, "height": h, "cells": cells}, ensure_ascii=False, indent=2), encoding="utf-8")

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    dr = ImageDraw.Draw(im)
    for a, b in zip(cells, cells[1:]):
        dr.line((a["x"] / 100 * w, a["y"] / 100 * h, b["x"] / 100 * w, b["y"] / 100 * h), fill=(0, 255, 255), width=2)
    for c in cells:
        px, py = c["x"] / 100 * w, c["y"] / 100 * h
        dr.ellipse((px - 6, py - 6, px + 6, py + 6), outline=(255, 0, 255), width=2)
        if c["n"] % 5 == 0 or c["n"] in (1, 2, 3, 8, 12, 100):
            dr.text((px + 7, py - 8), str(c["n"]), fill=(255, 255, 0))
    im.save(DBG)

    jumps = [
        (((a["x"] - b["x"]) * w / 100) ** 2 + ((a["y"] - b["y"]) * h / 100) ** 2) ** 0.5
        for a, b in zip(cells, cells[1:])
    ]
    print("count", len(cells), "mean/max", round(sum(jumps) / len(jumps), 1), round(max(jumps), 1))
    print("big", [(i + 1, round(j, 1)) for i, j in enumerate(jumps) if j > 40][:20])


if __name__ == "__main__":
    main()
