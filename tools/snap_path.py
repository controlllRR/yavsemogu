"""Detect orange circle centers, order by hand-tuned guide path, snap & export."""
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
CAND = ROOT / "game" / "peaks-debug.png"

# Hand-tuned guide along the REAL printed path (percent), denser at turns.
# Built from crop inspection of board-map.jpg.
GUIDE = [
    # 1–5 under Смоленск, then paw-prints up
    (17.0, 22.0),
    (19.5, 26.0),
    (23.0, 29.5),
    (27.0, 30.5),
    (31.0, 27.5),
    # 6–12 up toward fountain / kids right
    (34.5, 20.0),
    (38.0, 14.5),
    (42.0, 12.0),
    (46.5, 11.5),
    (50.0, 14.0),
    (52.0, 18.5),
    (53.0, 23.5),  # ~12 green
    (50.5, 27.5),
    # 14–21 left toward deer / kids
    (46.5, 30.0),
    (42.0, 31.5),
    (37.5, 32.5),
    (33.0, 33.5),  # ~17 purple
    (29.0, 35.5),
    (25.5, 38.5),
    (23.0, 42.5),
    (22.0, 47.0),
    # 22–28 loop left then right to green 28
    (21.0, 52.0),
    (23.5, 56.5),
    (28.0, 58.5),
    (33.0, 57.5),
    (37.5, 55.0),
    (41.0, 52.0),
    (44.5, 49.0),  # ~28 green
    # 29–34 right under carousel / dog
    (48.5, 47.5),
    (53.0, 47.0),
    (57.0, 48.5),
    (60.0, 51.5),
    (61.0, 55.5),
    (58.5, 59.0),
    # 35–41 down left to tower / purple 41
    (54.5, 61.5),
    (50.0, 64.0),
    (45.0, 67.0),
    (40.0, 70.5),
    (35.5, 74.0),
    (32.0, 78.0),
    (30.0, 82.5),  # ~41 purple
    # 42–49 along bottom past samovar to green 49
    (33.5, 86.0),
    (38.5, 87.5),
    (44.0, 86.5),
    (49.0, 84.0),
    (53.5, 81.5),
    (58.0, 80.0),
    (62.5, 81.0),
    (67.0, 83.5),  # ~49 green
    # 50–60 up then around church / purple 60
    (70.5, 81.0),
    (73.5, 76.5),
    (75.0, 71.5),
    (74.0, 66.5),
    (71.0, 62.5),
    (67.5, 60.0),
    (64.0, 58.5),
    (61.0, 56.0),
    (59.5, 52.0),
    (61.0, 48.0),
    (64.5, 46.0),  # ~60 purple
    # 61–70 curve around church to green 70
    (69.0, 46.5),
    (73.5, 49.0),
    (77.0, 53.0),
    (79.5, 58.0),
    (81.0, 63.5),
    (82.0, 69.0),
    (83.5, 74.0),
    (85.5, 70.0),
    (86.5, 64.5),
    (86.0, 59.0),  # ~70 green
    # 71–78 up right past firebird to purple 78
    (84.0, 54.0),
    (81.5, 49.5),
    (79.0, 45.5),
    (77.5, 41.0),
    (78.5, 36.5),
    (81.0, 33.0),
    (84.0, 31.0),
    (86.5, 34.5),  # ~78 purple
    # 79–83 toward cat / green 83
    (85.0, 39.0),
    (81.5, 41.5),
    (77.5, 40.0),
    (74.0, 36.5),
    (72.0, 32.0),  # ~83 green
    # 84–90 to purple 90 near house
    (71.5, 27.5),
    (73.5, 23.5),
    (77.0, 21.5),
    (81.0, 20.5),
    (84.5, 19.5),
    (87.0, 17.5),
    (85.0, 14.5),  # ~90 purple
    # 91–100 finish at izba
    (81.5, 13.5),
    (78.0, 14.5),
    (75.0, 17.0),
    (73.5, 20.5),
    (75.5, 24.0),
    (79.0, 25.5),
    (82.5, 24.0),
    (85.5, 21.5),
    (87.5, 18.5),
    (89.0, 15.5),  # 100
]


def detect_centers(bgr: np.ndarray) -> list[tuple[float, float]]:
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    orange = cv2.inRange(hsv, (4, 80, 110), (30, 255, 255))
    green = cv2.inRange(hsv, (38, 50, 70), (95, 255, 235))
    purple = cv2.inRange(hsv, (112, 35, 60), (165, 255, 225))
    mask = cv2.bitwise_or(orange, cv2.bitwise_or(green, purple))
    mask[0:42, :] = 0
    # fill digit holes
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    blur = cv2.GaussianBlur(mask, (5, 5), 0)
    circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, 1.15, 12, param1=70, param2=10, minRadius=7, maxRadius=15
    )
    pts: list[tuple[float, float]] = []
    if circles is None:
        return pts
    for x, y, r in np.round(circles[0]).astype(int):
        if x < 15 or y < 48 or x > w - 15 or y > h - 10:
            continue
        # require warm/special ring
        ok = 0
        for ang in range(0, 360, 40):
            px = int(x + r * 0.55 * np.cos(np.deg2rad(ang)))
            py = int(y + r * 0.55 * np.sin(np.deg2rad(ang)))
            if 0 <= px < w and 0 <= py < h and mask[py, px] > 0:
                ok += 1
        if ok < 4:
            continue
        pts.append((float(x), float(y)))
    # dedup
    pts.sort(key=lambda p: (p[1], p[0]))
    kept: list[tuple[float, float]] = []
    for p in pts:
        if any((p[0] - k[0]) ** 2 + (p[1] - k[1]) ** 2 < 10**2 for k in kept):
            continue
        kept.append(p)
    return kept


def densify(guide: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    seg = [0.0]
    for a, b in zip(guide, guide[1:]):
        seg.append(seg[-1] + ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)
    total = seg[-1] or 1
    out = []
    for k in range(n):
        t = total * k / (n - 1)
        j = 0
        while j < len(seg) - 1 and seg[j + 1] < t:
            j += 1
        if j >= len(guide) - 1:
            out.append(guide[-1])
            continue
        u = 0 if seg[j + 1] == seg[j] else (t - seg[j]) / (seg[j + 1] - seg[j])
        out.append(
            (
                guide[j][0] + (guide[j + 1][0] - guide[j][0]) * u,
                guide[j][1] + (guide[j + 1][1] - guide[j][1]) * u,
            )
        )
    return out


def main() -> None:
    bgr = cv2.imread(str(IMG))
    h, w = bgr.shape[:2]
    centers = detect_centers(bgr)
    print("centers", len(centers))

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    dr = ImageDraw.Draw(im)
    for p in centers:
        dr.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), outline=(0, 255, 180), width=2)
    im.save(CAND)

    guide_px = [(g[0] / 100 * w, g[1] / 100 * h) for g in densify(GUIDE, 100)]

    used = set()
    snapped: list[tuple[float, float]] = []
    for gx, gy in guide_px:
        best_i, best_d = None, 1e18
        for i, (cx, cy) in enumerate(centers):
            if i in used:
                continue
            d = (cx - gx) ** 2 + (cy - gy) ** 2
            if d < best_d:
                best_d, best_i = d, i
        # only snap if reasonably close (< ~4.5% of width)
        if best_i is not None and best_d < (0.045 * w) ** 2:
            snapped.append(centers[best_i])
            used.add(best_i)
        else:
            snapped.append((gx, gy))

    # If we have unused centers that are clearly on-path gaps, insert later via debug

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
            "x": round(100 * p[0] / w, 3),
            "y": round(100 * p[1] / h, 3),
            "kind": specials.get(i, "orange"),
        }
        for i, p in enumerate(snapped, 1)
    ]
    OUT.write_text(json.dumps({"width": w, "height": h, "cells": cells}, ensure_ascii=False, indent=2), encoding="utf-8")

    im2 = Image.fromarray(rgb)
    dr2 = ImageDraw.Draw(im2)
    for a, b in zip(cells, cells[1:]):
        dr2.line((a["x"] / 100 * w, a["y"] / 100 * h, b["x"] / 100 * w, b["y"] / 100 * h), fill=(0, 255, 255), width=2)
    for c in cells:
        px, py = c["x"] / 100 * w, c["y"] / 100 * h
        dr2.ellipse((px - 6, py - 6, px + 6, py + 6), outline=(255, 0, 255), width=2)
        dr2.text((px + 6, py - 8), str(c["n"]), fill=(255, 255, 0))
    im2.save(DBG)
    print("wrote", OUT, DBG)
    # how many snapped vs guide-only
    n_snap = sum(1 for i, p in enumerate(snapped) if i in range(len(centers)))  # rough
    print("used centers", len(used), "/", len(centers))


if __name__ == "__main__":
    main()
