"""Filters written inside the query: one search box for the CLI and the web UI.

    "type:pdf after:2026-01 ערבות"        -> text "ערבות", PDFs dated 2026-01-01 or later
    'folder:"kids" lang:he טיול'          -> under kids/, Hebrew documents
    "סוג:pdf תיקייה:home אחריות"           -> the same keys in Hebrew

The filters become a `where` callable that ragkit applies BEFORE ranking (in BM25, in the
vector store and therefore in the hybrid), so a filtered search still returns k results from
the allowed files instead of k results of which most are thrown away afterwards.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

KEYS = {"type": "type", "folder": "folder", "after": "after", "before": "before", "lang": "lang",
        "סוג": "type", "תיקייה": "folder", "תיקיה": "folder", "אחרי": "after", "לפני": "before",
        "שפה": "lang"}
TYPES = {"pdf": "pdf", "docx": "docx", "doc": "docx", "word": "docx", "md": "md", "markdown": "md",
         "txt": "txt", "text": "txt", "html": "html", "htm": "html", "web": "html", "image": "image",
         "img": "image", "png": "image", "jpg": "image", "scan": "image"}
LANGS = {"he": "he", "en": "en", "עברית": "he", "אנגלית": "en", "hebrew": "he", "english": "en"}
TOKEN = re.compile(r'(?<!\S)([^\s:"]+):(?:"([^"]*)"|(\S+))')
DATE = re.compile(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$")


@dataclass
class ParsedQuery:
    text: str
    filters: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def norm_date(value: str) -> Optional[str]:
    m = DATE.match(value.strip())
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1)
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def parse_query(q: str) -> ParsedQuery:
    """Reference implementation (see mine.parse_query for the contract)."""
    filters: dict = {}
    warnings: list[str] = []
    keep: list[str] = []
    pos = 0
    for m in TOKEN.finditer(q):
        key = KEYS.get(m.group(1).lower())
        if key is None:
            continue
        keep.append(q[pos:m.start()])
        pos = m.end()
        value = m.group(2) if m.group(2) is not None else m.group(3)
        if key == "type":
            for v in value.split(","):
                t = TYPES.get(v.strip().lower())
                if t:
                    filters.setdefault("type", [])
                    if t not in filters["type"]:
                        filters["type"].append(t)
                else:
                    warnings.append(f"unknown type {v!r}")
        elif key == "folder":
            for v in value.split(","):
                v = v.strip().strip("/").lower()
                if v:
                    filters.setdefault("folder", []).append(v)
        elif key in ("after", "before"):
            d = norm_date(value)
            if d:
                filters[key] = d
            else:
                warnings.append(f"bad date {value!r} (use YYYY, YYYY-MM or YYYY-MM-DD)")
                keep.append(m.group(0))
        elif key == "lang":
            lang = LANGS.get(value.strip().lower())
            if lang:
                filters["lang"] = lang
            else:
                warnings.append(f"unknown language {value!r}")
    keep.append(q[pos:])
    text = " ".join("".join(keep).split())
    return ParsedQuery(text=text, filters=filters, warnings=warnings)


def where_from(filters: dict) -> Optional[Callable]:
    """The filters as a ragkit `where` callable over chunk metadata, or None."""
    if not filters:
        return None
    types = set(filters.get("type") or [])
    folders = [f.lower() for f in filters.get("folder") or []]
    after, before, lang = filters.get("after"), filters.get("before"), filters.get("lang")

    def ok(chunk) -> bool:
        m = chunk.meta
        if types and m.get("format") not in types:
            return False
        if folders:
            fid = str(m.get("file", chunk.doc_id)).lower()
            if not any(fid == f or fid.startswith(f + "/") for f in folders):
                return False
        d = m.get("date") or ""
        if after and d < after:
            return False
        if before and d >= before:
            return False
        if lang and m.get("language") != lang:
            return False
        return True

    return ok
