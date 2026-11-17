"""Hand-mapped cell centers (percent) for board-map — tuned to printed numbers."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "images" / "board-map.jpg"
OUT = ROOT / "game" / "cells.json"
DBG = ROOT / "game" / "cells-debug.png"

# 100 points mapped to printed circles (landmarks from board inspection).
CELLS = [
    # 1–11: Смоленск → вверх к фонтану
    (16.8, 22.2),
    (19.5, 26.0),
    (22.8, 29.4),
    (26.6, 30.8),
    (30.4, 28.2),  # 5 near kids
    (33.8, 22.4),
    (37.4, 16.0),
    (41.6, 12.4),  # 8 purple near fountain left
    (46.0, 11.2),
    (50.0, 12.8),
    (52.6, 17.0),  # 11
    # 12–21: green 12 вниз/влево к оленю
    (53.6, 22.0),  # 12 green
    (51.2, 26.6),
    (47.4, 29.4),  # 14 near carousel left
    (43.2, 30.8),
    (38.8, 31.8),
    (34.6, 33.2),  # 17 purple
    (30.6, 35.6),  # 18 near kids bottom
    (27.0, 39.0),
    (24.2, 43.0),
    (22.4, 47.4),  # 21 near deer
    # 22–34: петля у оленя / кота → green 28 → вправо
    (21.4, 52.0),
    (22.8, 56.6),
    (26.6, 58.8),
    (31.2, 58.2),
    (35.6, 55.6),
    (39.6, 52.4),
    (43.4, 49.2),  # 28 green
    (47.4, 47.2),
    (51.8, 46.6),
    (56.0, 47.8),
    (59.2, 51.0),
    (60.4, 55.2),
    (58.2, 59.0),  # 34
    # 35–48: вниз к башне / purple 41 / вдоль самовара
    (54.4, 61.8),
    (50.0, 64.6),
    (45.4, 67.6),
    (40.8, 71.0),
    (36.4, 74.8),
    (33.0, 78.8),
    (30.8, 83.2),  # 41 purple at tower base
    (33.4, 86.8),
    (38.2, 88.0),
    (43.4, 86.8),
    (48.4, 84.2),
    (53.2, 81.6),
    (57.8, 80.0),
    (62.4, 80.8),  # 48
    # 49–61: green 49 → вверх к льву / purple 60
    (66.8, 83.2),  # 49 green
    (70.6, 81.0),
    (73.8, 76.8),
    (75.4, 71.8),
    (74.6, 66.6),
    (71.4, 62.6),
    (67.8, 60.0),
    (64.2, 58.2),
    (61.0, 55.6),
    (59.4, 51.6),
    (61.0, 47.6),
    (64.8, 45.6),  # 60 purple near lion
    (69.2, 46.2),  # 61
    # 62–74: вокруг церкви → green 70
    (73.6, 49.0),
    (77.2, 53.2),
    (79.8, 58.2),
    (81.4, 63.6),
    (82.4, 69.0),
    (84.0, 74.0),
    (86.0, 70.0),
    (87.0, 64.4),
    (86.4, 58.8),  # 70 green
    (84.4, 53.8),
    (81.8, 49.2),
    (79.2, 45.0),
    (77.6, 40.6),  # 74
    # 75–83: жар-птица → purple 78 → green 83 у карусели
    (78.6, 36.0),
    (81.4, 32.6),
    (84.6, 30.8),
    (87.0, 34.4),  # 78 purple
    (85.4, 38.8),
    (81.8, 41.2),
    (77.8, 39.8),
    (74.2, 36.2),
    (72.2, 31.6),  # 83 green near carousel top-right
    # 84–100: к коту / purple 90 / изба
    (71.6, 27.0),
    (73.6, 23.0),
    (77.2, 21.0),
    (81.2, 20.0),
    (84.8, 18.8),
    (87.4, 16.8),
    (85.4, 13.8),  # 90 purple near cat statue
    (81.6, 12.8),
    (78.0, 13.8),
    (74.8, 16.4),
    (73.2, 20.0),
    (75.4, 23.6),
    (79.0, 25.2),
    (82.8, 23.8),
    (86.0, 21.2),
    (88.0, 18.2),
    (89.4, 15.2),  # 100
]

SPECIALS = {
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


def main() -> None:
    assert len(CELLS) == 100, len(CELLS)
    img = Image.open(IMG).convert("RGB")
    w, h = img.size
    cells = [
        {"n": i, "x": round(p[0], 3), "y": round(p[1], 3), "kind": SPECIALS.get(i, "orange")}
        for i, p in enumerate(CELLS, 1)
    ]
    OUT.write_text(json.dumps({"width": w, "height": h, "cells": cells}, ensure_ascii=False, indent=2), encoding="utf-8")
    dr = ImageDraw.Draw(img)
    for a, b in zip(cells, cells[1:]):
        dr.line((a["x"] / 100 * w, a["y"] / 100 * h, b["x"] / 100 * w, b["y"] / 100 * h), fill=(0, 255, 255), width=2)
    for c in cells:
        px, py = c["x"] / 100 * w, c["y"] / 100 * h
        col = {"orange": "#ff9800", "green": "#22c55e", "purple": "#c084fc"}[c["kind"]]
        dr.ellipse((px - 7, py - 7, px + 7, py + 7), outline=col, width=3)
        dr.text((px + 8, py - 8), str(c["n"]), fill=(255, 255, 0))
    img.save(DBG)
    print("wrote", OUT, "cells", len(cells))


if __name__ == "__main__":
    main()
