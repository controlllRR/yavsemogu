"""Strict orange-disk detection for board cells."""
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

    # Warm orange/gold discs (main path)
    orange = cv2.inRange(hsv, (6, 90, 110), (28, 255, 255))
    # Green specials
    green = cv2.inRange(hsv, (35, 50, 70), (95, 255, 255))
    # Purple/blue specials
    purple = cv2.inRange(hsv, (115, 40, 60), (165, 255, 255))

    mask = cv2.bitwise_or(orange, cv2.bitwise_or(green, purple))
    # Kill large illustration areas by eroding then finding small components
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    # Remove title / borders
    mask[0:48, :] = 0
    mask[:, 0:8] = 0
    mask[:, w - 8 :] = 0
    mask[h - 6 :, :] = 0

    # Distance transform peaks as circle centers
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    # Local maxima
    kernel = 15
    dil = cv2.dilate(dist, np.ones((kernel, kernel), np.uint8))
    peaks = (dist == dil) & (dist >= 6.0)
    ys, xs = np.where(peaks)
    pts = list(zip(xs.tolist(), ys.tolist(), dist[ys, xs].tolist()))
    # Keep strongest peaks, dedup
    pts.sort(key=lambda t: -t[2])
    kept = []
    for x, y, r in pts:
        if any((x - kx) ** 2 + (y - ky) ** 2 < 14**2 for kx, ky, _ in kept):
            continue
        if r < 6 or r > 18:
            continue
        kept.append((x, y, r))
    print("peaks", len(kept))

    def kind_at(x: int, y: int) -> str:
        # sample ring
        vals = []
        for ang in range(0, 360, 30):
            rr = max(4, int(dist[y, x] * 0.6))
            px = int(x + rr * np.cos(np.deg2rad(ang)))
            py = int(y + rr * np.sin(np.deg2rad(ang)))
            if 0 <= px < w and 0 <= py < h:
                vals.append(hsv[py, px])
        if not vals:
            return "orange"
        mh = float(np.median([v[0] for v in vals]))
        if 35 <= mh <= 95:
            return "green"
        if 115 <= mh <= 165:
            return "purple"
        return "orange"

    centers = [(float(x), float(y), float(r), kind_at(int(x), int(y))) for x, y, r in kept]

    # Path order: start near Смоленск cell1 ~ (17%, 21%)
    sx, sy = 0.17 * w, 0.21 * h
    start = min(centers, key=lambda c: (c[0] - sx) ** 2 + (c[1] - sy) ** 2)
    ordered = [start]
    rest = [c for c in centers if c is not start]
    while rest:
        last = ordered[-1]
        if len(ordered) >= 2:
            prev = ordered[-2]
            vx, vy = last[0] - prev[0], last[1] - prev[1]
            n = (vx * vx + vy * vy) ** 0.5 or 1
            vx, vy = vx / n, vy / n
        else:
            vx, vy = 1, 0.2

        def score(c):
            dx, dy = c[0] - last[0], c[1] - last[1]
            d = (dx * dx + dy * dy) ** 0.5
            align = 0 if d < 1 else (dx * vx + dy * vy) / d
            # hard prefer close
            return d * d - 400 * max(0, align)

        # among 8 nearest by distance, pick best score
        by_dist = sorted(rest, key=lambda c: (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2)
        pool = by_dist[:8]
        nxt = min(pool, key=score)
        # if jump huge, still take nearest
        dmin = ((nxt[0] - last[0]) ** 2 + (nxt[1] - last[1]) ** 2) ** 0.5
        if dmin > 80:
            nxt = by_dist[0]
        ordered.append(nxt)
        rest.remove(nxt)

    # Orient finish near house
    ex, ey = 0.78 * w, 0.18 * h
    if (ordered[0][0] - ex) ** 2 + (ordered[0][1] - ey) ** 2 < (ordered[-1][0] - ex) ** 2 + (
        ordered[-1][1] - ey
    ) ** 2:
        ordered.reverse()

    # Keep only first 100 along path if more; if fewer, keep all
    if len(ordered) > 100:
        # Find contiguous segment of 100 with minimal max-edge
        # Simple: drop most isolated until 100
        while len(ordered) > 100:
            # remove point creating largest adjacent jump (not endpoints if possible)
            worst_i, worst_d = 1, -1.0
            for i in range(1, len(ordered) - 1):
                d1 = ((ordered[i][0] - ordered[i - 1][0]) ** 2 + (ordered[i][1] - ordered[i - 1][1]) ** 2) ** 0.5
                d2 = ((ordered[i][0] - ordered[i + 1][0]) ** 2 + (ordered[i][1] - ordered[i + 1][1]) ** 2) ** 0.5
                d = d1 + d2
                # also check shortcut without it
                skip = ((ordered[i - 1][0] - ordered[i + 1][0]) ** 2 + (ordered[i - 1][1] - ordered[i + 1][1]) ** 2) ** 0.5
                gain = d - skip
                if gain > worst_d:
                    worst_d, worst_i = gain, i
            ordered.pop(worst_i)

    specials = {12: "green", 28: "green", 49: "green", 70: "green", 83: "green", 8: "purple", 17: "purple", 41: "purple", 60: "purple", 78: "purple", 90: "purple"}
    cells = []
    for i, c in enumerate(ordered, 1):
        kind = specials.get(i, "orange")
        cells.append({"n": i, "x": round(100 * c[0] / w, 3), "y": round(100 * c[1] / h, 3), "kind": kind})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"width": w, "height": h, "cells": cells}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("count", len(cells))

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    dr = ImageDraw.Draw(im)
    for a, b in zip(cells, cells[1:]):
        dr.line((a["x"]/100*w, a["y"]/100*h, b["x"]/100*w, b["y"]/100*h), fill=(255,255,255), width=1)
    for c in cells:
        px, py = c["x"]/100*w, c["y"]/100*h
        col = {"orange":"#ff9800","green":"#22c55e","purple":"#c084fc"}[c["kind"]]
        dr.ellipse((px-5,py-5,px+5,py+5), outline=col, width=2)
        dr.text((px-4, py-14), str(c["n"]), fill="white")
    im.save(DBG)
    jumps = [(((a["x"]-b["x"])*w/100)**2+((a["y"]-b["y"])*h/100)**2)**0.5 for a,b in zip(cells,cells[1:])]
    print("jump mean/max", round(sum(jumps)/len(jumps),1), round(max(jumps),1))
    print("big", [(i+1, round(j,1)) for i,j in enumerate(jumps) if j>50][:20])


if __name__ == "__main__":
    main()
