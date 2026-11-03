"""Build hub/course-hub.html: the whole course hub as ONE self-contained HTML file.

    python hub/build_hub.py

Sources live in hub/src/ (index.html, course.js, lessons/NN.js, aids/lNN.js). Edit those,
then rebuild. Every <script src="..."> pointing at a local file is inlined; the result
opens straight from disk (file://) in any modern browser, no server needed. Progress
(stations done, quiz scores) is kept in the browser's localStorage, per browser.
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
OUT = HERE / "course-hub.html"

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
