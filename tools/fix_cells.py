"""Detect large path circles and order them with landmark anchors."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
# Use clean board (no green overlay markers from failed attempts)
IMG = ROOT / "images" / "board-map.jpg"
if not IMG.exists():
    IMG = ROOT / "images" / "board-marked.jpg"
OUT = ROOT / "game" / "cells.json"
DBG = ROOT / "game" / "cells-debug.png"
PEAKS = ROOT / "game" / "peaks-debug.png"


def detect_circles(bgr: np.ndarray) -> list[tuple[float, float]]:
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # Path cells: warm orange OR teal-green special OR purple special
    orange = cv2.inRange(hsv, (5, 100, 120), (28, 255, 255))
    green = cv2.inRange(hsv, (40, 60, 80), (95, 255, 230))
    purple = cv2.inRange(hsv, (115, 45, 70), (160, 255, 220))
    mask = cv2.bitwise_or(orange, cv2.bitwise_or(green, purple))

    # Kill known illustration blobs (percent → px)
    carves_pct = [
        (40, 62, 18, 20),  # samovar
        (78, 38, 18, 22),  # firebird
        (45, 32, 14, 16),  # carousel
        (22, 36, 12, 14),  # deer
        (10, 62, 10, 20),  # tower body
        (68, 55, 14, 18),  # church domes
        (32, 4, 30, 10),  # title
    ]
    for xp, yp, wp, hp in carves_pct:
        x, y = int(xp / 100 * w), int(yp / 100 * h)
        bw, bh = int(wp / 100 * w), int(hp / 100 * h)
        mask[y : y + bh, x : x + bw] = 0

    mask[0:45, :] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    mask = cv2.GaussianBlur(mask, (5, 5), 0)

    circles = cv2.HoughCircles(
        mask,
        cv2.HOUGH_GRADIENT,
        dp=1.0,
        minDist=14,
        param1=90,
        param2=9,
        minRadius=8,
        maxRadius=16,
    )
    pts: list[tuple[float, float]] = []
    if circles is None:
        return pts

    for x, y, r in np.round(circles[0]).astype(int):
        if x < 18 or y < 50 or x > w - 18 or y > h - 12:
            continue
        # fill ratio inside circle on original orange/green/purple mask
        yy, xx = np.ogrid[-r : r + 1, -r : r + 1]
        disk = xx * xx + yy * yy <= (r * 0.85) ** 2
        y0, x0 = y - r, x - r
        patch = mask[max(0, y0) : y + r + 1, max(0, x0) : x + r + 1]
        # rebuild disk aligned
        if patch.size == 0:
            continue
        # sample center ring color from BGR
        ring_ok = 0
        for ang in range(0, 360, 45):
            px = int(x + (r * 0.55) * np.cos(np.deg2rad(ang)))
            py = int(y + (r * 0.55) * np.sin(np.deg2rad(ang)))
            if 0 <= px < w and 0 <= py < h and mask[py, px] > 0:
                ring_ok += 1
        if ring_ok < 4:
            continue
        pts.append((float(x), float(y)))

    # Dedup
    pts.sort(key=lambda p: (p[1], p[0]))
    kept: list[tuple[float, float]] = []
    for p in pts:
        if any((p[0] - k[0]) ** 2 + (p[1] - k[1]) ** 2 < 11**2 for k in kept):
            continue
        kept.append(p)
    return kept


def chain_by_anchors(
    pts: list[tuple[float, float]], anchors_pct: list[tuple[float, float]], w: int, h: int
) -> list[tuple[float, float]]:
    """Split path into segments between anchors; NN within each segment's leftover pool."""
    anchors_xy = [(a[0] / 100 * w, a[1] / 100 * h) for a in anchors_pct]
    # Map each anchor to nearest unused point
    remaining = pts[:]
    anchor_pts: list[tuple[float, float]] = []
    for ax, ay in anchors_xy:
        if not remaining:
            break
        best = min(remaining, key=lambda p: (p[0] - ax) ** 2 + (p[1] - ay) ** 2)
        anchor_pts.append(best)
        remaining = [p for p in remaining if p is not best]

    if len(anchor_pts) < 2:
        return pts

    ordered: list[tuple[float, float]] = []
    pool = remaining[:]

    def nn_path(start: tuple[float, float], end: tuple[float, float], pool_local: list) -> list:
        """Greedy path from start toward end, consuming nearby points."""
        path = [start]
        local = pool_local[:]
        # Estimate how many points belong to this segment by distance budget
        while local:
            last = path[-1]
            # Prefer points that progress toward end
            scored = []
            for p in local:
                d_last = ((p[0] - last[0]) ** 2 + (p[1] - last[1]) ** 2) ** 0.5
                d_end = ((p[0] - end[0]) ** 2 + (p[1] - end[1]) ** 2) ** 0.5
                d_end_last = ((last[0] - end[0]) ** 2 + (last[1] - end[1]) ** 2) ** 0.5
                progress = d_end_last - d_end
                scored.append((d_last - 0.6 * progress, d_last, p))
            scored.sort()
            # Stop if next best is farther than remaining straight to end *and* end is close
            cand_d = scored[0][1]
            to_end = ((last[0] - end[0]) ** 2 + (last[1] - end[1]) ** 2) ** 0.5
            if to_end < 35 and cand_d > to_end * 0.9:
                break
            if cand_d > 70 and to_end < cand_d:
                break
            pick = scored[0][2]
            # Don't go past end too far
            if ((pick[0] - end[0]) ** 2 + (pick[1] - end[1]) ** 2) ** 0.5 < 8:
                break
            path.append(pick)
            local.remove(pick)
        path.append(end)
        # Return consumed (excluding start/end which are anchors)
        consumed = path[1:-1]
        return consumed, local

    # First anchor starts
    ordered.append(anchor_pts[0])
    pool_work = pool[:]
    for i in range(len(anchor_pts) - 1):
        a, b = anchor_pts[i], anchor_pts[i + 1]
        mid, pool_work = nn_path(a, b, pool_work)
        ordered.extend(mid)
        ordered.append(b)

    # Append any leftover by inserting on nearest edge
    for p in pool_work:
        best_i, best_cost = 0, 1e18
        for i in range(len(ordered) - 1):
            a, b = ordered[i], ordered[i + 1]
            cost = (
                ((a[0] - p[0]) ** 2 + (a[1] - p[1]) ** 2) ** 0.5
                + ((p[0] - b[0]) ** 2 + (p[1] - b[1]) ** 2) ** 0.5
                - ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            )
            if cost < best_cost:
                best_cost, best_i = cost, i
        ordered.insert(best_i + 1, p)

    # Dedup sequential duplicates
    clean = [ordered[0]]
    for p in ordered[1:]:
        if (p[0] - clean[-1][0]) ** 2 + (p[1] - clean[-1][1]) ** 2 > 4:
            clean.append(p)
    return clean


def main() -> None:
    bgr = cv2.imread(str(IMG))
    h, w = bgr.shape[:2]
    pts = detect_circles(bgr)
    print("detected", len(pts))

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    dr = ImageDraw.Draw(im)
    for p in pts:
        dr.ellipse((p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5), outline=(0, 255, 128), width=2)
    im.save(PEAKS)
    print("wrote", PEAKS)

    # Landmark anchors along the printed path (percent), tuned to board-map.jpg
    anchors = [
        (16.8, 21.8),  # 1
        (40.0, 23.0),  # ~8
        (51.0, 24.0),  # ~11 kids
        (28.0, 45.0),  # ~20 deer area
        (48.0, 42.0),  # ~28
        (58.0, 40.0),  # ~33 carousel
        (32.0, 72.0),  # ~42 tower
        (52.0, 76.0),  # ~49 samovar
        (78.0, 72.0),  # ~60 church
        (82.0, 50.0),  # ~70
        (75.0, 42.0),  # ~78 firebird
        (68.0, 30.0),  # ~85 cat
        (86.0, 18.0),  # 100 house
    ]

    ordered = chain_by_anchors(pts, anchors, w, h)
    print("ordered", len(ordered))

    # Force start/end to closest to anchors
    start_t = (anchors[0][0] / 100 * w, anchors[0][1] / 100 * h)
    end_t = (anchors[-1][0] / 100 * w, anchors[-1][1] / 100 * h)
    if (ordered[0][0] - end_t[0]) ** 2 + (ordered[0][1] - end_t[1]) ** 2 < (
        ordered[0][0] - start_t[0]
    ) ** 2 + (ordered[0][1] - start_t[1]) ** 2:
        ordered.reverse()

    # Resample to exactly 100 by arc-length (if count != 100)
    def densify(points, n):
        if len(points) < 2:
            return points
        seg = [0.0]
        for a, b in zip(points, points[1:]):
            seg.append(seg[-1] + ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)
        total = seg[-1] or 1
        out = []
        for k in range(n):
            t = total * k / (n - 1)
            j = 0
            while j < len(seg) - 1 and seg[j + 1] < t:
                j += 1
            if j >= len(points) - 1:
                out.append(points[-1])
                continue
            u = 0 if seg[j + 1] == seg[j] else (t - seg[j]) / (seg[j + 1] - seg[j])
            out.append(
                (
                    points[j][0] + (points[j + 1][0] - points[j][0]) * u,
                    points[j][1] + (points[j + 1][1] - points[j][1]) * u,
                )
            )
        return out

    # Prefer snapping: if we have close to 100 points, trim/pad by remove/insert rather than resample
    if abs(len(ordered) - 100) <= 15:
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
            ordered.insert(longest_i + 1, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
        samples = ordered
    else:
        print("resample densify from", len(ordered))
        samples = densify(ordered, 100)

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
        for i, p in enumerate(samples, 1)
    ]
    OUT.write_text(json.dumps({"width": w, "height": h, "cells": cells}, ensure_ascii=False, indent=2), encoding="utf-8")

    im2 = Image.fromarray(rgb)
    dr2 = ImageDraw.Draw(im2)
    for a, b in zip(cells, cells[1:]):
        dr2.line((a["x"] / 100 * w, a["y"] / 100 * h, b["x"] / 100 * w, b["y"] / 100 * h), fill=(0, 255, 255), width=2)
    for c in cells:
        px, py = c["x"] / 100 * w, c["y"] / 100 * h
        dr2.ellipse((px - 6, py - 6, px + 6, py + 6), outline=(255, 0, 255), width=2)
        if c["n"] % 5 == 0 or c["n"] in (1, 2, 3, 100):
            dr2.text((px + 7, py - 8), str(c["n"]), fill=(255, 255, 0))
    im2.save(DBG)
    jumps = [
        (((a["x"] - b["x"]) * w / 100) ** 2 + ((a["y"] - b["y"]) * h / 100) ** 2) ** 0.5
        for a, b in zip(cells, cells[1:])
    ]
    print("final", len(cells), "jump mean/max", round(sum(jumps) / len(jumps), 1), round(max(jumps), 1))
    print("big", [(i + 1, round(j, 1)) for i, j in enumerate(jumps) if j > 40][:25])


if __name__ == "__main__":
    main()
