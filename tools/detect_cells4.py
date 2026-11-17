"""HoughCircles on cell-color mask with large-illustration regions excluded."""
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

    mask = cv2.inRange(hsv, (5, 80, 100), (28, 255, 255))
    mask = cv2.bitwise_or(mask, cv2.inRange(hsv, (38, 55, 70), (95, 255, 255)))
    mask = cv2.bitwise_or(mask, cv2.inRange(hsv, (115, 40, 55), (165, 255, 255)))

    # Carve out large illustration blobs (approx regions on 1024x724)
    # samovar bottom-center, firebird right, carousel mid, deer, etc.
    carve = [
        (430, 470, 120, 120),  # samovar
        (820, 300, 160, 160),  # firebird
        (470, 250, 110, 110),  # carousel
        (250, 280, 90, 90),  # deer
        (700, 420, 100, 120),  # church gold domes partly
        (120, 480, 80, 140),  # tower
        (350, 40, 280, 70),  # title area leftover
    ]
    for x, y, bw, bh in carve:
        mask[y : y + bh, x : x + bw] = 0

    mask[0:50, :] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    mask = cv2.GaussianBlur(mask, (5, 5), 0)

    circles = cv2.HoughCircles(
        mask,
        cv2.HOUGH_GRADIENT,
        dp=1.0,
        minDist=16,
        param1=100,
        param2=10,
        minRadius=7,
        maxRadius=16,
    )
    pts = []
    if circles is not None:
        for x, y, r in np.round(circles[0]).astype(int):
            if mask[y, x] < 40:
                continue
            pts.append((float(x), float(y), float(r)))
    print("hough", len(pts))

    # Dedup
    pts.sort(key=lambda c: -c[2])
    kept = []
    for c in pts:
        if any((c[0] - k[0]) ** 2 + (c[1] - k[1]) ** 2 < 12**2 for k in kept):
            continue
        kept.append(c)
    print("kept", len(kept))

    # Save raw points debug
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    dr = ImageDraw.Draw(im)
    for c in kept:
        dr.ellipse((c[0] - 5, c[1] - 5, c[0] + 5, c[1] + 5), outline="#00ffaa", width=2)
    im.save(ROOT / "game" / "peaks-debug.png")

    # Path: repeatedly attach nearest unused within maxDist, with backtracking-ish restart
    sx, sy = 0.17 * w, 0.22 * h
    start = min(kept, key=lambda c: (c[0] - sx) ** 2 + (c[1] - sy) ** 2)

    def build(max_jump: float):
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
                vx, vy = 1, 0.2
            scored = []
            for c in rest:
                dx, dy = c[0] - last[0], c[1] - last[1]
                d = (dx * dx + dy * dy) ** 0.5
                align = 0 if d < 1 else (dx * vx + dy * vy) / d
                scored.append((d - 12 * max(0, align), d, c))
            scored.sort()
            # pick best under max_jump, else nearest
            pick = None
            for s, d, c in scored:
                if d <= max_jump:
                    pick = c
                    break
            if pick is None:
                pick = scored[0][2]
            ordered.append(pick)
            rest.remove(pick)
        return ordered

    ordered = build(55)
    ex, ey = 0.78 * w, 0.18 * h
    if (ordered[0][0] - ex) ** 2 + (ordered[0][1] - ey) ** 2 < (ordered[-1][0] - ex) ** 2 + (
        ordered[-1][1] - ey
    ) ** 2:
        ordered = list(reversed(ordered))

    # Trim to 100 by removing least useful interior points
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

    # If fewer than 100, duplicate? No — interpolate extras along long edges
    while len(ordered) < 100:
        # find longest edge and insert midpoint
        longest_i, longest_d = 0, -1.0
        for i in range(len(ordered) - 1):
            a, b = ordered[i], ordered[i + 1]
            d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            if d > longest_d:
                longest_d, longest_i = d, i
        a, b = ordered[longest_i], ordered[longest_i + 1]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        ordered.insert(longest_i + 1, mid)

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
    OUT.parent.mkdir(parents=True, exist_ok=True)
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
    print("count", len(cells), "jump mean/max", round(sum(jumps) / len(jumps), 1), round(max(jumps), 1))
    print("big", [(i + 1, round(j, 1)) for i, j in enumerate(jumps) if j > 45][:25])


if __name__ == "__main__":
    main()
