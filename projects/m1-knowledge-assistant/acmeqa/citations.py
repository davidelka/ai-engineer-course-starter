"""Citations: from "[2]" in the model's text to a passage the user can open.

The model writes numbers; the code owns what they mean. Each [n] is checked against the
sources that were ACTUALLY sent (a number outside 1..len(context) is an invented citation),
and each valid one becomes a Citation with the exact span: chunk offsets into the cleaned
document text, so GET /docs/{doc_id}?start=..&end=.. highlights precisely what the answer used.

resolve_citations is milestone 5 of the project (mine.py). This is the reference.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Optional, Sequence

from ragkit.clean import collapse_ws
from ragkit.types import Hit

CITE_RE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
SNIPPET_CHARS = 240


@dataclass
class Citation:
    n: int
    valid: bool
    doc_id: Optional[str] = None
    chunk_id: Optional[str] = None
    title: Optional[str] = None
    section: Optional[str] = None
    effective_date: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    snippet: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def snippet_of(text: str, limit: int = SNIPPET_CHARS) -> str:
    t = collapse_ws(text)
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def resolve_citations(text: str, context: Sequence[Hit]) -> list[Citation]:
    out: list[Citation] = []
    seen: set[int] = set()
    for m in CITE_RE.finditer(text):
        for part in re.split(r"[,;]", m.group(1)):
            n = int(part.strip())
            if n in seen:
                continue
            seen.add(n)
            if 1 <= n <= len(context):
                c = context[n - 1].chunk
                out.append(Citation(n=n, valid=True, doc_id=c.doc_id, chunk_id=c.id, title=c.title,
                                    section=c.section or None, effective_date=c.effective_date or None,
                                    start=c.start, end=c.end, snippet=snippet_of(c.text)))
            else:
                out.append(Citation(n=n, valid=False))
    return out
