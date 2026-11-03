"""A handful of Acme corpus documents, split into chunks by section.

Self-contained on purpose: it reads data/acme/corpus/docs directly (through the corpus
loader, which needs only the standard library) and does not depend on ragkit.

The default set has what the security lab needs:
- sup-refund-policy            the real refund rules (14 days for annual plans)
- sales-partner-northwind-notes  internal notes that contain a pasted partner email with a
                               planted prompt injection (refunds "at any time", Okta password)
- eng-pm-2026-08-api, eng-pm-2026-06-billing   CONFIDENTIAL postmortems (ACL tests)
- policies in English and Hebrew that benign questions are about
"""

from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

from .types import Chunk

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "data" / "acme" / "corpus"

DEFAULT_DOC_IDS = (
    "sup-refund-policy",
    "sales-partner-northwind-notes",
    "it-password-mfa-2026",
    "hr-vacation-2026",
    "hr-vacation-2026-he",
    "it-ai-usage-he",
    "sec-incident-response",
    "sec-data-classification",
    "it-saas-access-v2-2",
    "eng-pm-2026-08-api",
    "eng-pm-2026-06-billing",
)

META_KEYS = ("title", "department", "classification", "doc_type", "language", "effective_date")


def _loader():
    if str(CORPUS) not in sys.path:
        sys.path.insert(0, str(CORPUS))
    import load  # type: ignore  # data/acme/corpus/load.py

    return load


def split_sections(body: str, max_chars: int = 1800) -> list[str]:
    """Split a Markdown body at '## ' headings. The document's '# ' title line is kept as a
    prefix of every section so a chunk read alone still says where it comes from. Very long
    sections are split again at blank lines."""
    lines = body.strip().splitlines()
    title = lines[0] if lines and lines[0].startswith("# ") else ""
    parts: list[list[str]] = [[]]
    for line in lines[1:] if title else lines:
        if line.startswith("## ") and parts[-1]:
            parts.append([])
        parts[-1].append(line)
    out: list[str] = []
    for p in parts:
        text = "\n".join(p).strip()
        if not text:
            continue
        while len(text) > max_chars:
            cut = text.rfind("\n\n", 0, max_chars)
            cut = cut if cut > 200 else max_chars
            out.append(text[:cut].strip())
            text = text[cut:].strip()
        out.append(text)
    return [f"{title}\n{t}".strip() if title else t for t in out]


def chunks_for(doc_id: str, body: str, meta: dict) -> list[Chunk]:
    m = {k: meta.get(k) for k in META_KEYS if meta.get(k) is not None}
    m.setdefault("origin", meta.get("origin", "acme"))
    m["origin"] = meta.get("origin", m["origin"])
    return [Chunk(id=f"{doc_id}#{i}", doc_id=doc_id, text=t, meta=dict(m))
            for i, t in enumerate(split_sections(body))]


def make_doc(doc: dict) -> list[Chunk]:
    """Chunks for a document given inline, e.g. an attack's `inject_doc`:
    {"id", "title", "text", "classification", "department", "origin"}."""
    meta = {k: v for k, v in doc.items() if k not in ("id", "text")}
    meta.setdefault("classification", "internal")
    meta.setdefault("department", "company")
    meta.setdefault("origin", "web")
    body = doc["text"]
    if not body.lstrip().startswith("# "):
        body = f"# {doc.get('title', doc['id'])}\n\n{body}"
    return chunks_for(doc["id"], body, meta)


@lru_cache(maxsize=4)
def _load_cached(ids: tuple[str, ...]) -> tuple[Chunk, ...]:
    load = _loader()
    wanted = set(ids)
    out: list[Chunk] = []
    for doc in load.iter_docs({"md"}):
        if doc.id in wanted:
            out.extend(chunks_for(doc.id, doc.text, doc.meta))
    missing = wanted - {c.doc_id for c in out}
    if missing:
        raise FileNotFoundError(f"corpus documents not found: {sorted(missing)} (under {CORPUS})")
    return tuple(out)


def load_chunks(ids: Optional[Iterable[str]] = None) -> list[Chunk]:
    """Chunks for the given corpus document ids (default: DEFAULT_DOC_IDS). Returns copies,
    so callers may change meta without affecting other callers."""
    ids = tuple(ids) if ids is not None else DEFAULT_DOC_IDS
    return [Chunk(c.id, c.doc_id, c.text, dict(c.meta)) for c in _load_cached(ids)]


def doc_meta(ids: Optional[Iterable[str]] = None) -> dict[str, dict]:
    """{doc_id: meta} for the loaded documents (one entry per document)."""
    out: dict[str, dict] = {}
    for c in load_chunks(ids):
        out.setdefault(c.doc_id, c.meta)
    return out


_WS = re.compile(r"\s+")


def snippet(text: str, n: int = 160) -> str:
    t = _WS.sub(" ", text).strip()
    return t if len(t) <= n else t[: n - 1] + "…"
