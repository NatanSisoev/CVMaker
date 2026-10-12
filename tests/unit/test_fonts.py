"""Every font the stylesheet references must exist (no 404s on first paint)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_every_font_face_url_points_at_a_real_file():
    css = (ROOT / "static/src/app.css").read_text(encoding="utf-8")
    urls = re.findall(r"url\('/static/(fonts/[^']+)'\)", css)
    assert len(urls) == 3
    for rel in urls:
        path = ROOT / "static" / rel
        assert path.is_file() and path.stat().st_size > 10_000, rel
        assert path.read_bytes()[:4] == b"wOF2", rel  # WOFF2 magic number
