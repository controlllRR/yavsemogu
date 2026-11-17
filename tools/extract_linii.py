"""Extract and split the Линии в ритме HTML into our stack files."""
from __future__ import annotations

import base64
import re
from pathlib import Path

SRC = Path(r"C:\Users\anton\Downloads\AyuGram Desktop\igra_linii_v_ritme_robot_ispravleno.html")
OUT_DIR = Path(r"c:\Users\anton\Documents\yavsemogu\games\linii")
ASSETS = OUT_DIR / "assets"


def main() -> None:
    text = SRC.read_text(encoding="utf-8", errors="replace")
    print("chars", len(text))

    style_m = re.search(r"<style>(.*?)</style>", text, re.S)
    style = style_m.group(1) if style_m else ""
    print("style chars", len(style))

    # Extract data URIs from CSS and HTML
    ASSETS.mkdir(parents=True, exist_ok=True)
    asset_map: dict[str, str] = {}
    n = 0

    def save_data_uri(match: re.Match[str]) -> str:
        nonlocal n
        full = match.group(0)
        mime = match.group(1)
        b64 = match.group(2)
        ext = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/webp": "webp",
            "image/svg+xml": "svg",
            "image/gif": "gif",
            "audio/mpeg": "mp3",
            "audio/wav": "wav",
            "font/woff2": "woff2",
        }.get(mime.split(";")[0].strip(), "bin")
        n += 1
        name = f"asset-{n:02d}.{ext}"
        path = ASSETS / name
        path.write_bytes(base64.b64decode(b64))
        rel = f"assets/{name}"
        asset_map[full] = rel
        print("saved", name, path.stat().st_size, mime)
        return f"url({rel})"

    # url(data:...)
    style2 = re.sub(
        r"url\(\s*['\"]?data:([^;,]+(?:;[^,]*)?);base64,([A-Za-z0-9+/=\s]+)['\"]?\s*\)",
        save_data_uri,
        style,
        flags=re.I,
    )

    # body/html without style/script first
    body_m = re.search(r"<body[^>]*>(.*)</body>", text, re.S | re.I)
    body = body_m.group(1) if body_m else ""

    # Replace data URIs in body attrs
    def save_attr(match: re.Match[str]) -> str:
        nonlocal n
        attr = match.group(1)
        mime = match.group(2)
        b64 = match.group(3)
        ext = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/webp": "webp",
            "image/svg+xml": "svg",
            "image/gif": "gif",
        }.get(mime.split(";")[0].strip(), "bin")
        n += 1
        name = f"asset-{n:02d}.{ext}"
        (ASSETS / name).write_bytes(base64.b64decode(b64))
        print("saved attr", name, mime)
        return f'{attr}="assets/{name}"'

    body2 = re.sub(
        r"(src|href)=['\"]data:([^;,]+(?:;[^,]*)?);base64,([A-Za-z0-9+/=\s]+)['\"]",
        save_attr,
        body,
        flags=re.I,
    )

    scripts = list(re.finditer(r"<script([^>]*)>(.*?)</script>", text, re.S | re.I))
    print("scripts", len(scripts))
    js_parts = []
    for i, m in enumerate(scripts):
        attrs, content = m.group(1), m.group(2)
        print(f"script {i} attrs={attrs!r} len={len(content)}")
        if content.strip():
            js_parts.append(content)

    js = "\n\n".join(js_parts)
    # strip body scripts for clean HTML later
    body_clean = re.sub(r"<script\b[^>]*>.*?</script>", "", body2, flags=re.S | re.I)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "_extracted.css").write_text(style2, encoding="utf-8")
    (OUT_DIR / "_extracted.js").write_text(js, encoding="utf-8")
    (OUT_DIR / "_extracted.body.html").write_text(body_clean, encoding="utf-8")
    print("css out", len(style2), "js out", len(js), "body", len(body_clean))
    print("assets", n)


if __name__ == "__main__":
    main()
