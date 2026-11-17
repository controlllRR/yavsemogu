"""Detect cells by orange ring + dark digit center, then NN path."""
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
ALL = ROOT / "game" / "peaks-debug.png"


def is_cell(bgr: np.ndarray, x: int, y: int, r: float = 10.0) -> tuple[bool, str]:
    h, w = bgr.shape[:2]
    if x < 20 or y < 50 or x > w - 20 or y > h - 15:
        return False, "orange"

    # Center should be relatively dark (digit) OR at least not pure orange flood
    cy0, cy1 = max(0, y - 3), min(h, y + 4)
    cx0, cx1 = max(0, x - 3), min(w, x + 4)
    center = bgr[cy0:cy1, cx0:cx1].astype(np.float32).reshape(-1, 3)
    cmean = center.mean(axis=0)  # BGR
    cbright = float(cmean.sum())

    # Ring samples
    ring = []
    bg = []
    for ang in range(0, 360, 20):
        rad = np.deg2rad(ang)
        rx = int(x + r * 0.7 * np.cos(rad))
        ry = int(y + r * 0.7 * np.sin(rad))
        bx = int(x + r * 1.7 * np.cos(rad))
        by = int(y + r * 1.7 * np.sin(rad))
        if 0 <= rx < w and 0 <= ry < h:
            ring.append(bgr[ry, rx].astype(np.float32))
        if 0 <= bx < w and 0 <= by < h:
            bg.append(bgr[by, bx].astype(np.float32))
    if len(ring) < 8 or len(bg) < 8:
        return False, "orange"

    ring_m = np.mean(ring, axis=0)
    bg_m = np.mean(bg, axis=0)
    rb, rg, rr = ring_m
    # Ring warm: R high, B low
    warm = rr > 140 and rr > rg and rr > rb + 40
    # Green special
    greenish = rg > rr + 10 and rg > rb + 10 and rg > 100
    # Purple special
    purplish = rb > rg + 5 and rr > 70 and rb > 80 and rg < 120

    if not (warm or greenish or purplish):
        return False, "orange"

    # Background darker than ring
    if float(bg_m.sum()) > float(ring_m.sum()) - 30:
        # still ok if bg is dark brown overall
        if float(bg_m.sum()) > 280:
            return False, "orange"

    # Center not brighter than ring (digit or same)
    if cbright > float(ring_m.sum()) + 40:
        return False, "orange"

    kind = "orange"
    if greenish:
        kind = "green"
    elif purplish:
        kind = "purple"
    return True, kind


def main() -> None:
    bgr = cv2.imread(str(IMG))
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    color = cv2.inRange(hsv, (5, 70, 90), (30, 255, 255))
    color = cv2.bitwise_or(color, cv2.inRange(hsv, (35, 40, 60), (100, 255, 255)))
    color = cv2.bitwise_or(color, cv2.inRange(hsv, (110, 35, 50), (170, 255, 255)))
    color = cv2.morphologyEx(color, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    color[0:48, :] = 0

    dist = cv2.distanceTransform(color, cv2.DIST_L2, 5)
    dil = cv2.dilate(dist, np.ones((13, 13), np.uint8))
    peaks = (dist == dil) & (dist >= 5.5)
    ys, xs = np.where(peaks)

    candidates = []
    for x, y in zip(xs.tolist(), ys.tolist()):
        r = float(dist[y, x])
        ok, kind = is_cell(bgr, x, y, r=max(8.0, r))
        if ok:
            candidates.append((float(x), float(y), r, kind))

    # Dedup
    candidates.sort(key=lambda c: -c[2])
    kept = []
    for c in candidates:
        if any((c[0] - k[0]) ** 2 + (c[1] - k[1]) ** 2 < 13**2 for k in kept):
            continue
        kept.append(c)
    print("candidates", len(kept))

    # Debug all peaks
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    dr = ImageDraw.Draw(im)
    for c in kept:
        dr.ellipse((c[0] - 4, c[1] - 4, c[0] + 4, c[1] + 4), outline="#00ff88", width=2)
    im.save(ALL)
    print("wrote", ALL)

    if len(kept) < 90:
        print("WARNING: too few cells")

    # Greedy path from start
    sx, sy = 0.168 * w, 0.215 * h
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
            vx, vy = 1, 0.15

        by_dist = sorted(rest, key=lambda c: (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2)
        best = None
        best_s = 1e18
        for c in by_dist[:10]:
            dx, dy = c[0] - last[0], c[1] - last[1]
            d = (dx * dx + dy * dy) ** 0.5
            align = 0 if d < 1 else (dx * vx + dy * vy) / d
            s = d - 14 * max(0, align)
            if d > 75:
                s += (d - 75) * 3
            if s < best_s:
                best_s, best = s, c
        ordered.append(best)
        rest.remove(best)

    ex, ey = 0.79 * w, 0.19 * h
    if (ordered[0][0] - ex) ** 2 + (ordered[0][1] - ey) ** 2 < (ordered[-1][0] - ex) ** 2 + (
        ordered[-1][1] - ey
    ) ** 2:
        ordered.reverse()

    # If more than 100, remove points that least hurt path continuity
    while len(ordered) > 100:
        worst_i, worst_gain = None, -1e9
        for i in range(1, len(ordered) - 1):
            a, b, c = ordered[i - 1], ordered[i], ordered[i + 1]
            d_ab = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            d_bc = ((b[0] - c[0]) ** 2 + (b[1] - c[1]) ** 2) ** 0.5
            d_ac = ((a[0] - c[0]) ** 2 + (a[1] - c[1]) ** 2) ** 0.5
            gain = d_ab + d_bc - d_ac
            if gain > worst_gain:
                worst_gain, worst_i = gain, i
        ordered.pop(worst_i)

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
    print("count", len(cells))

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
    print("jump mean/max", round(sum(jumps) / len(jumps), 1), round(max(jumps), 1))
    print("big", [(i + 1, round(j, 1)) for i, j in enumerate(jumps) if j > 48])


if __name__ == "__main__":
    main()
