"""PDF with pypdf: extract per page, remove running headers/footers, rebuild paragraphs.

A PDF has no paragraphs, headings or tables: only glyphs at positions (pypdf's docs say so
in as many words). Everything structural here is a reconstruction, and each step can fail:

1. Extraction. mode="layout" keeps the visual arrangement, so table rows stay on one line
   ("Enterprise   below 99.95% ...   10%"); mode="plain" (pypdf's default) emits each table
   cell on its own line, and the row is gone.
2. Header/footer removal: lines that repeat at the top/bottom of most pages (digits
   ignored, so "Page 1"/"Page 2" match) are dropped, plus bare page numbers.
3. Layout clean-up: indentation stripped; runs of 3+ spaces inside a line become " | " so
   a table row reads "Enterprise | below 99.95% but at least 99.5% | 10%".
4. Paragraphs: lines are joined back into paragraphs (blank lines are kept as paragraph
   breaks); "1. Uptime commitment" style lines become '## ' headings, and the first
   short line becomes the '# ' title, so the heading-aware chunker works on PDFs too.
5. De-hyphenation of words broken at line ends.

pymupdf (AGPL) is faster and often better on complex layouts; pypdf is pure Python and
BSD-licensed, which is why the course uses it. Scanned PDFs need OCR: neither helps.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from ..clean import dehyphenate, repeated_lines, strip_lines
from .base import LoadResult

NUM_HEADING_RE = re.compile(r"^(\d+(\.\d+)*)\.\s+[A-Zא-ת][^.:;!?]{0,70}$")
TABLE_GAP_RE = re.compile(r" {3,}")


def _extract_pages(data: bytes, mode: str) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for p in reader.pages:
        if mode == "layout":
            pages.append(p.extract_text(extraction_mode="layout", layout_mode_space_vertically=False))
        else:
            pages.append(p.extract_text())
    return pages


def _layout_line(line: str) -> str:
    line = line.strip()
    if TABLE_GAP_RE.search(line):
        line = TABLE_GAP_RE.sub(" | ", line)
    return line


def _rebuild(lines: list[str], *, detect_headings: bool) -> str:
    """Join wrapped lines into paragraphs; keep table rows, list items and headings as lines."""
    blocks: list[str] = []
    para: list[str] = []
    title_done = False

    def flush():
        if para:
            blocks.append(" ".join(para))
            para.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            flush()
            continue
        is_row = " | " in line
        is_item = bool(re.match(r"^([-•*]|\(?[a-z]\))\s", line))
        if detect_headings and not title_done and not para and not is_row and len(line) < 90 \
                and not line.endswith("."):
            flush()
            blocks.append("# " + line)
            title_done = True
            continue
        title_done = True
        if detect_headings and NUM_HEADING_RE.match(line) and not is_row:
            flush()
            blocks.append("## " + line)
            continue
        if is_row or is_item:
            flush()
            if blocks and (" | " in blocks[-1] or re.match(r"^([-•*])\s", blocks[-1])):
                blocks[-1] += "\n" + line
            else:
                blocks.append(line)
            continue
        last = blocks[-1].split("\n")[-1] if blocks else ""
        if not para and " | " in last:
            cells = last.split(" | ")
            open_cells = [i for i, c in enumerate(cells) if c.count("(") > c.count(")")]
            if open_cells:                      # a wrapped table cell: "(London, ... Paris," + "Tokyo)"
                cells[open_cells[0]] += " " + line
                blocks[-1] = blocks[-1][: len(blocks[-1]) - len(last)] + " | ".join(cells)
                continue
        para.append(line)
    flush()
    return "\n\n".join(blocks)


def load_pdf(path: Path, data: bytes, *, mode: str = "layout", remove_headers: bool = True,
             detect_headings: bool = True) -> LoadResult:
    pages = _extract_pages(data, mode)
    raw = "\n\n".join(pages)
    removed: list[str] = []
    if remove_headers:
        keys = repeated_lines(pages)
        cleaned = []
        for page in pages:
            text, gone = strip_lines(page, keys)
            removed += gone
            cleaned.append(text)
        pages = cleaned
    text = "\n\n".join(pages)
    text = dehyphenate(text)
    lines = [(_layout_line(ln) if mode == "layout" else ln.strip()) for ln in text.split("\n")]
    text = _rebuild(lines, detect_headings=detect_headings)
    meta = {"pages": len(pages)}
    m = re.match(r"# (.+)", text)
    if m:
        meta["title"] = m.group(1).strip()
    return LoadResult(text=text, meta=meta, raw_text=raw, removed=removed)
