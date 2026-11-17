"""Detect and order the 100 board cells more reliably."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
IMG_PATH = ROOT / "images" / "board-map.jpg"
OUT_JSON = ROOT / "game" / "cells.json"
OUT_DEBUG = ROOT / "game" / "cells-debug.png"


def cell_mask(bgr: np.ndarray) -> np.ndarray:
    """Mask warm orange cells + green/purple specials."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    orange = ((h >= 5) & (h <= 30) & (s >= 80) & (v >= 120))
    green = ((h >= 35) & (h <= 95) & (s >= 60) & (v >= 80))
    purple = (((h >= 110) & (h <= 170)) & (s >= 40) & (v >= 70))

    # Exclude huge illustration blobs later via size; keep mask soft
    mask = (orange | green | purple).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return mask


def classify(bgr: np.ndarray, x: int, y: int) -> str:
    hsv = cv2.cvtColor(bgr[y - 2 : y + 3, x - 2 : x + 3], cv2.COLOR_BGR2HSV)
    h = float(np.median(hsv[:, :, 0]))
    if 35 <= h <= 95:
        return "green"
    if 110 <= h <= 170:
        return "purple"
    return "orange"


def find_centers(bgr: np.ndarray) -> list[tuple[float, float, float, str]]:
    mask = cell_mask(bgr)
    h, w = mask.shape
    # Restrict a bit from edges/title
    mask[:35, :] = 0
    mask[:, :10] = 0
    mask[:, w - 10 :] = 0

    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    centers: list[tuple[float, float, float, str]] = []
    for i in range(1, n_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        bw = int(stats[i, cv2.CC_STAT_WIDTH])
        bh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if area < 55 or area > 900:
            continue
        if bw < 10 or bh < 10 or bw > 45 or bh > 45:
            continue
        aspect = bw / max(bh, 1)
        if aspect < 0.55 or aspect > 1.8:
            continue
        cx, cy = float(centroids[i][0]), float(centroids[i][1])
        # Circularity via contour
        comp = (labels == i).astype(np.uint8) * 255
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        peri = cv2.arcLength(cnts[0], True)
        circ = 0 if peri == 0 else 4 * np.pi * area / (peri * peri)
        if circ < 0.55:
            continue
        kind = classify(bgr, int(cx), int(cy))
        rad = 0.5 * (bw + bh) / 2
        centers.append((cx, cy, rad, kind))

    # Dedup
    centers.sort(key=lambda c: c[2], reverse=True)
    kept: list[tuple[float, float, float, str]] = []
    for c in centers:
        if any((c[0] - k[0]) ** 2 + (c[1] - k[1]) ** 2 < 12**2 for k in kept):
            continue
        kept.append(c)
    return kept


def nearest_path(centers: list[tuple[float, float, float, str]]) -> list[tuple[float, float, float, str]]:
    """Greedy path with local 2-opt cleanup, start near Смоленск (top-left)."""
    # Known approximate start from map layout
    start = min(centers, key=lambda c: (c[0] - 160) ** 2 + (c[1] - 150) ** 2)
    ordered = [start]
    rest = [c for c in centers if c is not start]

    while rest:
        last = ordered[-1]
        if len(ordered) >= 2:
            prev = ordered[-2]
            vx, vy = last[0] - prev[0], last[1] - prev[1]
            n = (vx * vx + vy * vy) ** 0.5 or 1.0
            vx, vy = vx / n, vy / n
        else:
            vx, vy = 1.0, 0.3

        # Candidates within reasonable distance; if none, take global nearest
        cands = []
        for c in rest:
            dx, dy = c[0] - last[0], c[1] - last[1]
            dist = (dx * dx + dy * dy) ** 0.5
            align = 0.0 if dist < 1 else (dx * vx + dy * vy) / dist
            cands.append((dist - 10 * max(0.0, align), dist, c))
        cands.sort(key=lambda t: t[0])
        # Prefer among nearby
        nearby = [t for t in cands if t[1] < 70]
        pick = (nearby or cands)[0][2]
        ordered.append(pick)
        rest.remove(pick)

    # 2-opt to remove crossings for a few passes
    def length(path: list) -> float:
        s = 0.0
        for a, b in zip(path, path[1:]):
            s += ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        return s

    improved = True
    passes = 0
    while improved and passes < 40:
        improved = False
        passes += 1
        for i in range(1, len(ordered) - 2):
            for j in range(i + 1, len(ordered) - 1):
                a, b = ordered[i - 1], ordered[i]
                c, d = ordered[j], ordered[j + 1]
                before = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 + (
                    (c[0] - d[0]) ** 2 + (c[1] - d[1]) ** 2
                ) ** 0.5
                after = ((a[0] - c[0]) ** 2 + (a[1] - c[1]) ** 2) ** 0.5 + (
                    (b[0] - d[0]) ** 2 + (b[1] - d[1]) ** 2
                ) ** 0.5
                if after + 0.5 < before:
                    ordered[i : j + 1] = reversed(ordered[i : j + 1])
                    improved = True
    return ordered


def main() -> None:
    bgr = cv2.imread(str(IMG_PATH))
    h, w = bgr.shape[:2]
    print("size", w, h)

    centers = find_centers(bgr)
    print("centers", len(centers))

    # If count is off, also merge with Hough for missing small cells
    if abs(len(centers) - 100) > 8:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, 1.2, 15, param1=70, param2=16, minRadius=8, maxRadius=20
        )
        extra = []
        if circles is not None:
            mask = cell_mask(bgr)
            for x, y, r in np.round(circles[0]).astype(int):
                if x < 12 or y < 35 or x > w - 12 or y > h - 8:
                    continue
                if mask[y, x] == 0:
                    # allow if neighborhood has mask
                    if mask[max(0, y - 4) : y + 5, max(0, x - 4) : x + 5].sum() < 255 * 6:
                        continue
                extra.append((float(x), float(y), float(r), classify(bgr, int(x), int(y))))
        allc = centers + extra
        allc.sort(key=lambda c: c[2], reverse=True)
        kept = []
        for c in allc:
            if any((c[0] - k[0]) ** 2 + (c[1] - k[1]) ** 2 < 13**2 for k in kept):
                continue
            kept.append(c)
        centers = kept
        print("merged centers", len(centers))

    # Trim or pad toward 100 by dropping farthest outliers from median path density
    if len(centers) > 100:
        # Drop points with unusually large nearest-neighbor distance repeatedly
        while len(centers) > 100:
            # score isolation
            scores = []
            for i, c in enumerate(centers):
                dists = sorted(
                    ((c[0] - o[0]) ** 2 + (c[1] - o[1]) ** 2) ** 0.5 for j, o in enumerate(centers) if i != j
                )
                scores.append((dists[0] + 0.5 * dists[1], i))
            scores.sort(reverse=True)
            # remove most isolated
            drop = scores[0][1]
            centers.pop(drop)

    ordered = nearest_path(centers)

    # Orient path so end is near wooden house (top-right ~ 820, 120)
    end_target = (820.0, 130.0)
    start_target = (165.0, 155.0)
    d_start = (ordered[0][0] - start_target[0]) ** 2 + (ordered[0][1] - start_target[1]) ** 2
    d_end = (ordered[-1][0] - start_target[0]) ** 2 + (ordered[-1][1] - start_target[1]) ** 2
    if d_end < d_start:
        ordered = list(reversed(ordered))
    # Ensure finish near house
    d_fin = (ordered[-1][0] - end_target[0]) ** 2 + (ordered[-1][1] - end_target[1]) ** 2
    d_fin_alt = (ordered[0][0] - end_target[0]) ** 2 + (ordered[0][1] - end_target[1]) ** 2
    if d_fin_alt < d_fin:
        ordered = list(reversed(ordered))

    cells = []
    for i, c in enumerate(ordered, start=1):
        cells.append(
            {
                "n": i,
                "x": round(100 * c[0] / w, 3),
                "y": round(100 * c[1] / h, 3),
                "kind": c[3],
            }
        )

    # Override kind by known specials if detection of kind drifted:
    # Greens: 12,28,49,70,83  Purples: 8,17,41,60,78,90 (from map description)
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
    for cell in cells:
        if cell["n"] in specials:
            cell["kind"] = specials[cell["n"]]
        elif cell["kind"] not in ("green", "purple"):
            cell["kind"] = "orange"

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps({"width": w, "height": h, "cells": cells}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("wrote", OUT_JSON, "count", len(cells))

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    dbg = Image.fromarray(rgb)
    draw = ImageDraw.Draw(dbg)
    for a, b in zip(cells, cells[1:]):
        draw.line(
            (a["x"] / 100 * w, a["y"] / 100 * h, b["x"] / 100 * w, b["y"] / 100 * h),
            fill=(255, 255, 255, 120),
            width=1,
        )
    for cell in cells:
        px, py = cell["x"] / 100 * w, cell["y"] / 100 * h
        color = {"orange": "#ff9800", "green": "#22c55e", "purple": "#a78bfa"}[cell["kind"]]
        draw.ellipse((px - 6, py - 6, px + 6, py + 6), outline=color, width=2)
        draw.text((px - 5, py - 16), str(cell["n"]), fill="#ffffff")
    dbg.save(OUT_DEBUG)
    print("wrote", OUT_DEBUG)

    jumps = [
        (((a["x"] - b["x"]) * w / 100) ** 2 + ((a["y"] - b["y"]) * h / 100) ** 2) ** 0.5
        for a, b in zip(cells, cells[1:])
    ]
    print("jump mean/max", round(sum(jumps) / len(jumps), 1), round(max(jumps), 1))
    print("big", [(i + 1, round(j, 1)) for i, j in enumerate(jumps) if j > 55])


if __name__ == "__main__":
    main()
