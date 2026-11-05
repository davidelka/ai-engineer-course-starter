"""Build hub/course-hub.html: the whole course hub as ONE self-contained HTML file.

    python hub/build_hub.py

Sources live in hub/src/ (index.html, course.js, lessons/NN.js, aids/lNN.js). Edit those,
then rebuild. Every <script src="..."> pointing at a local file is inlined; the result
opens straight from disk (file://) in any modern browser, no server needed. Progress
(stations done, quiz scores) is kept in the browser's localStorage, per browser.
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
OUT = HERE / "course-hub.html"
FONTS = SRC / "fonts"
LATIN = "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"
HEBREW = "U+0307-0308,U+0590-05FF,U+200C-2010,U+20AA,U+25CC,U+FB1D-FB4F"


def embedded_fonts() -> str:
    """@font-face rules with the woff2 files inlined (IBM Plex, SIL Open Font License 1.1, see fonts/OFL-IBM-Plex.txt)."""
    if not FONTS.is_dir():
        return ""
    rules = []
    faces = [("IBM Plex Sans Hebrew", "ibm-plex-sans-hebrew-hebrew-{w}-normal.woff2", HEBREW, (400, 500, 700)),
             ("IBM Plex Sans Hebrew", "ibm-plex-sans-hebrew-latin-{w}-normal.woff2", LATIN, (400, 500, 700)),
             ("IBM Plex Mono", "ibm-plex-mono-latin-{w}-normal.woff2", LATIN, (400, 600))]
    for family, pattern, rng, weights in faces:
        for w in weights:
            f = FONTS / pattern.format(w=w)
            if not f.exists():
                continue
            b64 = base64.b64encode(f.read_bytes()).decode()
            rules.append(f"@font-face{{font-family:'{family}';font-style:normal;font-display:swap;font-weight:{w};"
                         f"src:url(data:font/woff2;base64,{b64}) format('woff2');unicode-range:{rng};}}")
    return "<style>/* IBM Plex, SIL OFL 1.1 */" + "".join(rules) + "</style>" if rules else ""

TAG = re.compile(r'<script src="([^"?]+)(?:\?[^"]*)?"(?: defer)?></script>')

# Texts that only make sense inside the claude.ai artifact version of the hub.
REPLACE = {
    "ההורדה לא זמינה בתצוגה הזו. הקובץ ai-engineer-course.zip נמצא גם בצ'אט.":
        "הריפו מגיע יחד עם ה-hub: זו התיקייה ai-engineer-course שבה נמצא הקובץ הזה (hub/course-hub.html).",
    "בודק אם אפשר להוריד מכאן…": "",
    "<b>הגשה:</b> שלח לי בצ'אט": "<b>הגשה:</b> שלח ל-Claude בצ'אט",
}


def inline(match: re.Match) -> str:
    src = match.group(1)
    if src.startswith(("http:", "https:")) or src == "repo.js":
        return ""  # repo.js held a zip of lesson 1 for the artifact version; not needed here
    path = SRC / src
    if not path.exists():
        return ""
    code = path.read_text(encoding="utf-8").replace("</script", "<\\/script")
    return f"<script>/* {src} */\n{code}\n</script>"


def main() -> None:
    html = (SRC / "index.html").read_text(encoding="utf-8")
    html = TAG.sub(inline, html)
    fonts = embedded_fonts()
    if fonts:  # no network needed: drop the Google Fonts link and inline the same fonts
        html = re.sub(r'<link rel="stylesheet" href="https://fonts.googleapis.com/[^"]*">', fonts, html)
    for old, new in REPLACE.items():
        html = html.replace(old, new)
    if "<!doctype" not in html[:200].lower():
        html = ("<!doctype html>\n<html>\n<head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                "<title>מסלול AI Engineer</title></head>\n<body>\n" + html + "\n</body></html>\n")
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
