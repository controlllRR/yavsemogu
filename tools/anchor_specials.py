"""Find green/purple specials, orange cells; order path using known special numbers as anchors."""
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

GREEN_NS = [12, 28, 49, 70, 83]
PURPLE_NS = [8, 17, 41, 60, 78, 90]


def find_color_circles(bgr, lo, hi, name):
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lo, hi)
    mask[0:48, :] = 0
    # remove huge blobs (buildings)
    n, lab, st, cent = cv2.connectedComponentsWithStats(mask, 8)
    clean = np.zeros_like(mask)
    for i in range(1, n):
        area = int(st[i, cv2.CC_STAT_AREA])
        bw = int(st[i, cv2.CC_STAT_WIDTH])
        bh = int(st[i, cv2.CC_STAT_HEIGHT])
        if 70 <= area <= 550 and 11 <= bw <= 36 and 11 <= bh <= 36:
            clean[lab == i] = 255
    clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    blur = cv2.GaussianBlur(clean, (5, 5), 0)
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1.1, 14, param1=60, param2=8, minRadius=7, maxRadius=15)
    pts = []
    if circles is not None:
        for x, y, r in np.round(circles[0]).astype(int):
            if 18 < x < w - 18 and 50 < y < h - 10:
                if clean[y, x] > 0 or clean[max(0, y - 2) : y + 3, max(0, x - 2) : x + 3].sum() > 0:
                    pts.append((float(x), float(y)))
    # also use component centroids of right size
    n2, lab2, st2, cent2 = cv2.connectedComponentsWithStats(clean, 8)
    for i in range(1, n2):
        area = int(st2[i, cv2.CC_STAT_AREA])
        bw = int(st2[i, cv2.CC_STAT_WIDTH])
        bh = int(st2[i, cv2.CC_STAT_HEIGHT])
        if 80 <= area <= 480 and 12 <= bw <= 34 and 12 <= bh <= 34:
            aspect = bw / max(bh, 1)
            if 0.65 <= aspect <= 1.55:
                pts.append((float(cent2[i][0]), float(cent2[i][1])))
    kept = []
    for p in pts:
        if any((p[0] - k[0]) ** 2 + (p[1] - k[1]) ** 2 < 12**2 for k in kept):
            continue
        kept.append(p)
    print(name, len(kept))
    return kept


def find_orange(bgr):
    return find_color_circles(bgr, (5, 100, 120), (28, 255, 255), "orange")


def main():
    bgr = cv2.imread(str(IMG))
    h, w = bgr.shape[:2]

    greens = find_color_circles(bgr, (40, 60, 80), (95, 255, 230), "green")
    purples = find_color_circles(bgr, (115, 45, 70), (160, 255, 220), "purple")
    oranges = find_orange(bgr)

    # Save candidate debug
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    dr = ImageDraw.Draw(im)
    for p in oranges:
        dr.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), outline=(255, 160, 0), width=2)
    for p in greens:
        dr.ellipse((p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6), outline=(0, 255, 0), width=3)
    for p in purples:
        dr.ellipse((p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6), outline=(200, 100, 255), width=3)
    im.save(ROOT / "game" / "peaks-debug.png")

    # Need exactly 5 greens and 6 purples — pick best by size/position if more
    # Order specials along approximate path using known rough positions
    green_guess = {
        12: (53, 23),
        28: (44, 49),
        49: (67, 83),
        70: (86, 59),
        83: (72, 32),
    }
    purple_guess = {
        8: (41, 12),
        17: (34, 33),
        41: (31, 83),
        60: (65, 46),
        78: (87, 35),
        90: (85, 14),
    }

    def assign(pts, guesses):
        remaining = pts[:]
        mapping = {}
        for n, (gx, gy) in sorted(guesses.items(), key=lambda t: t[0]):
            tx, ty = gx / 100 * w, gy / 100 * h
            if not remaining:
                mapping[n] = (tx, ty)
                continue
            best = min(remaining, key=lambda p: (p[0] - tx) ** 2 + (p[1] - ty) ** 2)
            mapping[n] = best
            remaining = [p for p in remaining if p is not best]
        return mapping

    gmap = assign(greens, green_guess)
    pmap = assign(purples, purple_guess)
    print("green map", {k: (round(100 * v[0] / w, 1), round(100 * v[1] / h, 1)) for k, v in gmap.items()})
    print("purple map", {k: (round(100 * v[0] / w, 1), round(100 * v[1] / h, 1)) for k, v in pmap.items()})

    # All path points = orange + specials
    special_pts = set()
    anchors = {}  # n -> (x,y)
    for n, p in gmap.items():
        anchors[n] = p
        special_pts.add(p)
    for n, p in pmap.items():
        anchors[n] = p
        special_pts.add(p)

    all_pts = oranges[:]
    for p in special_pts:
        if not any((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 < 10**2 for q in all_pts):
            all_pts.append(p)
    print("all pts", len(all_pts))

    # Build path: start near 1, visit in order forcing anchors at their numbers
    # First order all points with NN from start
    start = min(all_pts, key=lambda p: (p[0] - 0.17 * w) ** 2 + (p[1] - 0.22 * h) ** 2)
    ordered = [start]
    rest = [p for p in all_pts if p is not start]
    while rest:
        last = ordered[-1]
        if len(ordered) >= 2:
            prev = ordered[-2]
            vx, vy = last[0] - prev[0], last[1] - prev[1]
            nrm = (vx * vx + vy * vy) ** 0.5 or 1
            vx, vy = vx / nrm, vy / nrm
        else:
            vx, vy = 1, 0.15
        scored = []
        for p in rest:
            dx, dy = p[0] - last[0], p[1] - last[1]
            d = (dx * dx + dy * dy) ** 0.5
            align = 0 if d < 1 else (dx * vx + dy * vy) / d
            scored.append((d - 14 * max(0, align) + (max(0, d - 48) * 3), p))
        scored.sort()
        pick = scored[0][1]
        ordered.append(pick)
        rest.remove(pick)

    end = (0.89 * w, 0.15 * h)
    if (ordered[0][0] - end[0]) ** 2 + (ordered[0][1] - end[1]) ** 2 < (
        ordered[-1][0] - end[0]
    ) ** 2 + (ordered[-1][1] - end[1]) ** 2:
        ordered.reverse()

    # Force-insert anchors at correct indices by rotating/splicing
    # Convert ordered list to cells of len ~N, then snap index of each special
    # Better approach: split path into segments between consecutive anchors

    anchor_order = sorted(anchors.keys())  # 8,12,17,...
    # Find each anchor in ordered list
    def nearest_idx(pt):
        return min(range(len(ordered)), key=lambda i: (ordered[i][0] - pt[0]) ** 2 + (ordered[i][1] - pt[1]) ** 2)

    # Rebuild: start -> ... -> a8 -> ... -> a12 -> ... -> end
    segments_targets = [1] + anchor_order + [100]

    # Get points for start and end
    start_pt = ordered[0]
    end_pt = min(ordered, key=lambda p: (p[0] - end[0]) ** 2 + (p[1] - end[1]) ** 2)

    # Extract subsequence between anchors from the NN path
    idx_map = {n: nearest_idx(anchors[n]) for n in anchor_order}
    print("anchor indices in NN path", idx_map)

    # If indices are not monotonic, fall back to segment NN between anchors only
    pts_pool = ordered[:]

    def path_between(a, b, pool, count_hint):
        """Greedy from a to b taking nearby points."""
        if a is b:
            return [a]
        local = [p for p in pool if p is not a and p is not b]
        path = [a]
        while local:
            last = path[-1]
            to_b = ((last[0] - b[0]) ** 2 + (last[1] - b[1]) ** 2) ** 0.5
            scored = []
            for p in local:
                d = ((p[0] - last[0]) ** 2 + (p[1] - last[1]) ** 2) ** 0.5
                d_b = ((p[0] - b[0]) ** 2 + (p[1] - b[1]) ** 2) ** 0.5
                progress = to_b - d_b
                scored.append((d - 0.7 * progress, d, d_b, p))
            scored.sort()
            # stop if better to go to b
            if scored[0][1] > to_b * 0.95 and to_b < 55:
                break
            if scored[0][1] > 70 and to_b < scored[0][1]:
                break
            pick = scored[0][3]
            path.append(pick)
            local.remove(pick)
            # safety
            if len(path) > count_hint + 15:
                break
        path.append(b)
        return path

    # Expected counts between anchors
    bounds = [1] + anchor_order + [100]
    final = [start_pt]
    pool = [p for p in all_pts if p is not start_pt]
    for i in range(len(bounds) - 1):
        n0, n1 = bounds[i], bounds[i + 1]
        need = n1 - n0  # number of steps from n0 to n1 inclusive of n1
        a = final[-1]
        if n1 == 100:
            b = end_pt
        elif n1 in anchors:
            b = anchors[n1]
        else:
            b = end_pt
        # remove a from pool already in final
        pool = [p for p in pool if not any((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 < 4 for q in final)]
        if n1 in anchors:
            pool = [p for p in pool if (p[0] - b[0]) ** 2 + (p[1] - b[1]) ** 2 > 4]

        seg = path_between(a, b, pool, need)
        # seg includes a and b; append without duplicating a
        for p in seg[1:]:
            final.append(p)
            pool = [q for q in pool if (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 > 4]

    # Now final has variable length; we need exactly 100 with anchors at right indices
    # Resample each segment to exact length
    # Rebuild segments by finding anchor positions in final
    def find_pt(pt):
        return min(range(len(final)), key=lambda i: (final[i][0] - pt[0]) ** 2 + (final[i][1] - pt[1]) ** 2)

    cells_pts = [None] * 100
    cells_pts[0] = start_pt
    cells_pts[99] = end_pt
    for n, p in anchors.items():
        cells_pts[n - 1] = p

    # Fill gaps by interpolating along final path arc between known indices
    known = sorted(i for i, p in enumerate(cells_pts) if p is not None)

    # Build arc-length mapping of final
    seg_len = [0.0]
    for a, b in zip(final, final[1:]):
        seg_len.append(seg_len[-1] + ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)

    def point_at_arc(t):  # t in [0,1]
        target = t * seg_len[-1]
        j = 0
        while j < len(seg_len) - 1 and seg_len[j + 1] < target:
            j += 1
        if j >= len(final) - 1:
            return final[-1]
        u = 0 if seg_len[j + 1] == seg_len[j] else (target - seg_len[j]) / (seg_len[j + 1] - seg_len[j])
        return (
            final[j][0] + (final[j + 1][0] - final[j][0]) * u,
            final[j][1] + (final[j + 1][1] - final[j][1]) * u,
        )

    # Map known indices to arc positions
    known_arc = {}
    for i in known:
        idx = find_pt(cells_pts[i])
        known_arc[i] = seg_len[idx] / (seg_len[-1] or 1)

    for a, b in zip(known, known[1:]):
        ta, tb = known_arc[a], known_arc[b]
        for i in range(a + 1, b):
            if cells_pts[i] is not None:
                continue
            u = (i - a) / (b - a)
            t = ta + (tb - ta) * u
            cells_pts[i] = point_at_arc(t)

    # Snap filled points to nearest unused orange if close
    used = set()
    for i, p in enumerate(cells_pts):
        if i + 1 in anchors or i in (0, 99):
            # keep anchor exact
            for j, q in enumerate(all_pts):
                if (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 < 9**2:
                    used.add(j)
            continue
        best_j, best_d = None, 1e18
        for j, q in enumerate(all_pts):
            if j in used:
                continue
            d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2
            if d < best_d:
                best_d, best_j = d, j
        if best_j is not None and best_d < (0.03 * w) ** 2:
            cells_pts[i] = all_pts[best_j]
            used.add(best_j)

    specials = {n: "green" for n in GREEN_NS} | {n: "purple" for n in PURPLE_NS}
    cells = [
        {
            "n": i,
            "x": round(100 * cells_pts[i - 1][0] / w, 3),
            "y": round(100 * cells_pts[i - 1][1] / h, 3),
            "kind": specials.get(i, "orange"),
        }
        for i in range(1, 101)
    ]
    OUT.write_text(json.dumps({"width": w, "height": h, "cells": cells}, ensure_ascii=False, indent=2), encoding="utf-8")

    im2 = Image.fromarray(rgb)
    dr2 = ImageDraw.Draw(im2)
    for a, b in zip(cells, cells[1:]):
        dr2.line((a["x"] / 100 * w, a["y"] / 100 * h, b["x"] / 100 * w, b["y"] / 100 * h), fill=(0, 255, 255), width=2)
    for c in cells:
        px, py = c["x"] / 100 * w, c["y"] / 100 * h
        col = {"orange": "#ff9800", "green": "#22c55e", "purple": "#c084fc"}[c["kind"]]
        dr2.ellipse((px - 6, py - 6, px + 6, py + 6), outline=col, width=2)
        if c["n"] % 5 == 0 or c["n"] in (1, 8, 12, 17, 28, 41, 49, 60, 70, 78, 83, 90, 100):
            dr2.text((px + 7, py - 8), str(c["n"]), fill=(255, 255, 0))
    im2.save(DBG)
    print("wrote", OUT)

    # verify specials colors
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    def det(x, y):
        vals = []
        for ang in range(0, 360, 30):
            px = int(x + 7 * np.cos(np.deg2rad(ang)))
            py = int(y + 7 * np.sin(np.deg2rad(ang)))
            if 0 <= px < w and 0 <= py < h:
                vals.append(int(hsv[py, px, 0]))
        mh = float(np.median(vals))
        if 35 <= mh <= 95:
            return "green"
        if 110 <= mh <= 170:
            return "purple"
        return "orange"

    for n in GREEN_NS + PURPLE_NS:
        c = cells[n - 1]
        print("check", n, det(c["x"] / 100 * w, c["y"] / 100 * h), "exp", c["kind"])


if __name__ == "__main__":
    main()
