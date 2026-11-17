"""Snap a guide path onto detected circle candidates; export cells.json."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CAND = json.loads((ROOT / "game" / "candidates.json").read_text(encoding="utf-8"))
IMG = ROOT / "images" / "board-map.jpg"
OUT = ROOT / "game" / "cells.json"
DBG = ROOT / "game" / "cells-debug.png"

# Dense guide along the printed path (percent). Order matters; coords are approximate —
# each point snaps to the nearest unused detected circle center.
GUIDE = [
    # 1–11 Смоленск → фонтан
    (16.5, 22.0), (19.0, 25.5), (22.2, 29.0), (26.0, 30.5), (29.8, 28.0),
    (33.2, 22.0), (36.8, 15.8), (41.0, 12.0), (45.5, 11.0), (49.5, 12.5), (52.2, 16.5),
    # 12–21
    (53.5, 21.5), (51.0, 26.2), (47.0, 29.2), (42.8, 30.8), (38.4, 31.8),
    (34.2, 33.2), (30.2, 35.8), (26.6, 39.2), (23.8, 43.2), (22.0, 47.6),
    # 22–34
    (21.0, 52.2), (22.5, 56.8), (26.4, 59.0), (31.0, 58.4), (35.4, 55.8),
    (39.4, 52.6), (43.2, 49.4), (47.2, 47.2), (51.6, 46.6), (56.0, 47.8),
    (59.2, 51.2), (60.4, 55.4), (58.0, 59.2),
    # 35–48
    (54.2, 62.0), (49.8, 64.8), (45.2, 67.8), (40.6, 71.2), (36.2, 75.0),
    (32.8, 79.0), (30.6, 83.4), (33.2, 87.0), (38.0, 88.2), (43.2, 87.0),
    (48.2, 84.4), (53.0, 81.8), (57.6, 80.2), (62.2, 81.0),
    # 49–61
    (66.6, 83.4), (70.4, 81.2), (73.6, 77.0), (75.2, 72.0), (74.4, 66.8),
    (71.2, 62.8), (67.6, 60.2), (64.0, 58.4), (60.8, 55.8), (59.2, 51.8),
    (60.8, 47.8), (64.6, 45.8), (69.0, 46.4),
    # 62–74
    (73.4, 49.2), (77.0, 53.4), (79.6, 58.4), (81.2, 63.8), (82.2, 69.2),
    (83.8, 74.2), (85.8, 70.2), (86.8, 64.6), (86.2, 59.0), (84.2, 54.0),
    (81.6, 49.4), (79.0, 45.2), (77.4, 40.8),
    # 75–83
    (78.4, 36.2), (81.2, 32.8), (84.4, 31.0), (86.8, 34.6), (85.2, 39.0),
    (81.6, 41.4), (77.6, 40.0), (74.0, 36.4), (72.0, 31.8),
    # 84–100
    (71.4, 27.2), (73.4, 23.2), (77.0, 21.2), (81.0, 20.2), (84.6, 19.0),
    (87.2, 17.0), (85.2, 14.0), (81.4, 13.0), (77.8, 14.0), (74.6, 16.6),
    (73.0, 20.2), (75.2, 23.8), (78.8, 25.4), (82.6, 24.0), (85.8, 21.4),
    (87.8, 18.4), (89.2, 15.4),
]

SPECIALS = {
    12: "green", 28: "green", 49: "green", 70: "green", 83: "green",
    8: "purple", 17: "purple", 41: "purple", 60: "purple", 78: "purple", 90: "purple",
}


def main() -> None:
    assert len(GUIDE) == 100, len(GUIDE)
    unused = list(range(len(CAND)))
    cells = []
    for i, (gx, gy) in enumerate(GUIDE, 1):
        best_j, best_d = None, 1e18
        for j in unused:
            c = CAND[j]
            d = (c["x"] - gx) ** 2 + (c["y"] - gy) ** 2
            if d < best_d:
                best_d, best_j = d, j
        # snap if within ~4% of board
        if best_j is not None and best_d < 4.0**2:
            c = CAND[best_j]
            unused.remove(best_j)
            x, y = c["x"], c["y"]
            snapped = True
        else:
            x, y = gx, gy
            snapped = False
        cells.append({"n": i, "x": x, "y": y, "kind": SPECIALS.get(i, "orange"), "snapped": snapped})

    n_snap = sum(1 for c in cells if c.pop("snapped"))
    print("snapped", n_snap, "/ 100, unused cand", len(unused))

    payload = {"width": 1024, "height": 724, "cells": cells}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    img = Image.open(IMG).convert("RGB")
    w, h = img.size
    dr = ImageDraw.Draw(img)
    for a, b in zip(cells, cells[1:]):
        dr.line((a["x"] / 100 * w, a["y"] / 100 * h, b["x"] / 100 * w, b["y"] / 100 * h), fill=(0, 255, 255), width=2)
    for c in cells:
        px, py = c["x"] / 100 * w, c["y"] / 100 * h
        col = {"orange": "#ff9800", "green": "#22c55e", "purple": "#c084fc"}[c["kind"]]
        dr.ellipse((px - 7, py - 7, px + 7, py + 7), outline=col, width=3)
        if c["n"] % 5 == 0 or c["n"] in (1, 2, 3, 8, 12, 100):
            dr.text((px + 8, py - 8), str(c["n"]), fill=(255, 255, 0))
    img.save(DBG)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
