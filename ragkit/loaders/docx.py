"""DOCX with python-docx: body paragraphs and tables in document order.

Headers and footers live in separate parts of a .docx (section.header / section.footer), so
they are simply not read into the body. They are reported in `removed`, and included in
`raw_text` (the "before" picture: header + body + footer, as a naive converter outputs).
Heading styles ("Heading 1".."Heading 6", "Title") become '#' headings, list styles become
'- ' items, and tables become 'a | b | c' rows, in the order they appear in the body.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from .base import LoadResult, table_rows_to_text


def load_docx(path: Path, data: bytes) -> LoadResult:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(io.BytesIO(data))
    blocks: list[str] = []
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, d)
            text = " ".join(p.text.split())
            if not text:
                continue
            style = (p.style.name if p.style is not None else "") or ""
            m = re.match(r"Heading (\d)", style)
            if style == "Title":
                blocks.append("# " + text)
            elif m:
                blocks.append("#" * int(m.group(1)) + " " + text)
            elif "List" in style:
                blocks.append("- " + text)
            else:
                blocks.append(text)
        elif tag == "tbl":
            t = Table(el, d)
            rows = [[c.text for c in r.cells] for r in t.rows]
            blocks.append(table_rows_to_text(rows))
    removed, header_lines, footer_lines = [], [], []
    for s in d.sections:
        for part, bucket in ((s.header, header_lines), (s.footer, footer_lines)):
            for p in part.paragraphs:
                if p.text.strip() and p.text.strip() not in bucket:
                    bucket.append(p.text.strip())
    removed = [f"header: {x}" for x in header_lines] + [f"footer: {x}" for x in footer_lines]
    body = "\n\n".join(blocks)
    raw = "\n".join(header_lines + [body] + footer_lines)
    meta = {}
    cp = d.core_properties
    if cp.title:
        meta["title"] = cp.title
    else:
        m = re.match(r"# (.+)", body)
        if m:
            meta["title"] = m.group(1)
    return LoadResult(text=body, meta=meta, raw_text=raw, removed=removed)
