"""Build 100 cell positions from hand-tuned waypoints along the board path."""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "images" / "board-map.jpg"
OUT = ROOT / "game" / "cells.json"
DBG = ROOT / "game" / "cells-debug.png"

# Waypoints in percent of image (x, y), following cells 1→100 on the printed map.
# Tuned to the winding orange path on board-map.jpg (1024×724).
WAYPOINTS = [
    # 1–11 top-left under Смоленск, then right
    (16.6, 21.5),
    (19.8, 24.8),
    (22.6, 28.2),
    (25.8, 30.5),
    (29.2, 28.8),
    (32.6, 26.4),
    (36.0, 24.2),
    (39.5, 23.0),
    (43.0, 22.2),
    (46.6, 21.5),
    (50.2, 23.0),
    # 12–20 down left around kids / deer
    (52.8, 26.5),
    (50.5, 30.5),
    (47.2, 33.8),
    (43.5, 35.5),
    (39.8, 36.2),
    (36.0, 37.5),
    (32.5, 39.5),
    (29.5, 42.5),
    (27.5, 46.5),
    # 21–30 left mid down toward tower / carousel approach
    (26.0, 50.5),
    (28.5, 54.0),
    (32.0, 56.5),
    (36.0, 57.5),
    (40.0, 56.0),
    (43.5, 53.0),
    (46.5, 49.5),
    (48.5, 45.5),
    (50.0, 41.5),
    (52.5, 38.5),
    # 31–42 center around carousel / dog then down
    (56.0, 37.0),
    (59.5, 38.5),
    (62.0, 42.0),
    (62.5, 46.5),
    (60.5, 50.5),
    (57.0, 53.5),
    (53.0, 55.5),
    (49.0, 57.5),
    (45.0, 60.0),
    (41.0, 63.0),
    (37.0, 66.5),
    (33.5, 70.0),
    # 43–55 bottom-left tower area across toward samovar
    (30.5, 73.5),
    (28.0, 77.5),
    (30.5, 81.0),
    (35.0, 82.5),
    (39.5, 81.5),
    (44.0, 79.5),
    (48.5, 77.5),
    (53.0, 76.0),
    (57.5, 77.5),
    (61.5, 80.5),
    (65.5, 82.5),
    # 56–68 bottom toward church
    (69.5, 81.0),
    (73.0, 78.0),
    (76.0, 74.5),
    (78.5, 70.5),
    (80.5, 66.0),
    (82.0, 61.5),
    (83.5, 57.0),
    (85.0, 52.5),
    (86.0, 48.0),
    (84.0, 44.0),
    (80.5, 42.0),
    (76.5, 43.5),
    # 69–82 right side / firebird / up
    (73.0, 46.5),
    (70.0, 50.0),
    (68.0, 54.5),
    (67.5, 59.5),
    (69.5, 64.0),
    (73.0, 66.5),
    (77.0, 65.0),
    (80.0, 61.0),
    (81.5, 56.0),
    (80.0, 51.0),
    (76.5, 48.0),
    (72.5, 46.0),
    (68.5, 43.0),
    (65.5, 39.0),
    # 83–100 toward cat / house finish
    (64.0, 34.5),
    (66.5, 30.5),
    (70.0, 28.0),
    (74.0, 26.5),
    (78.0, 25.5),
    (81.5, 24.0),
    (84.0, 21.5),
    (81.0, 18.5),
    (77.0, 17.0),
    (73.5, 16.5),
    (70.5, 18.5),
    (68.5, 22.0),
    (70.0, 25.5),
    (74.0, 27.0),
    (78.5, 26.0),
    (82.0, 23.5),
    (85.0, 20.5),
    (87.5, 17.5),
]


def catmull_rom(p0, p1, p2, p3, t: float):
    t2, t3 = t * t, t * t * t
    return (
        0.5
        * (
            (2 * p1[0])
            + (-p0[0] + p2[0]) * t
            + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
            + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
        ),
        0.5
        * (
            (2 * p1[1])
            + (-p0[1] + p2[1]) * t
            + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
            + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
        ),
    )


def densify(points: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    # Arc-length resample via dense Catmull-Rom samples
    pts = [points[0]] + points + [points[-1]]
    dense = []
    for i in range(1, len(pts) - 2):
        steps = 24
        for s in range(steps):
            dense.append(catmull_rom(pts[i - 1], pts[i], pts[i + 1], pts[i + 2], s / steps))
    dense.append(points[-1])

    # cumulative length
    seg = [0.0]
    for a, b in zip(dense, dense[1:]):
        seg.append(seg[-1] + math.hypot(a[0] - b[0], a[1] - b[1]))
    total = seg[-1] or 1.0
    out = []
    for k in range(n):
        target = total * k / (n - 1)
        # find segment
        j = 0
        while j < len(seg) - 1 and seg[j + 1] < target:
            j += 1
        if j >= len(dense) - 1:
            out.append(dense[-1])
            continue
        t = 0 if seg[j + 1] == seg[j] else (target - seg[j]) / (seg[j + 1] - seg[j])
        x = dense[j][0] + (dense[j + 1][0] - dense[j][0]) * t
        y = dense[j][1] + (dense[j + 1][1] - dense[j][1]) * t
        out.append((x, y))
    return out


def main() -> None:
    img = Image.open(IMG).convert("RGB")
    w, h = img.size
    samples = densify(WAYPOINTS, 100)
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
        {"n": i, "x": round(p[0], 3), "y": round(p[1], 3), "kind": specials.get(i, "orange")}
        for i, p in enumerate(samples, 1)
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"width": w, "height": h, "cells": cells}, ensure_ascii=False, indent=2), encoding="utf-8")

    dr = ImageDraw.Draw(img)
    for a, b in zip(cells, cells[1:]):
        dr.line((a["x"] / 100 * w, a["y"] / 100 * h, b["x"] / 100 * w, b["y"] / 100 * h), fill=(255, 255, 255), width=2)
    for c in cells:
        px, py = c["x"] / 100 * w, c["y"] / 100 * h
        col = {"orange": "#ff9800", "green": "#22c55e", "purple": "#c084fc"}[c["kind"]]
        dr.ellipse((px - 6, py - 6, px + 6, py + 6), outline=col, width=2)
        if c["n"] % 5 == 0 or c["n"] == 1:
            dr.text((px + 7, py - 7), str(c["n"]), fill="white")
    img.save(DBG)
    print("wrote", OUT, "and", DBG, "waypoints", len(WAYPOINTS))


if __name__ == "__main__":
    main()
