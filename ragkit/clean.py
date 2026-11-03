"""Cleaning and normalization: the boring step that decides whether a quote can be found.

normalize(text) runs on every document after its loader, and on every quote/query that is
compared against documents (ragkit.evaluate does that), so both sides look the same.

What it does, in order:
  1. Unicode NFC: "é" typed as e + combining accent becomes one code point.
  2. Removes invisible characters: zero-width spaces, BOM, soft hyphens, and the bidi
     control marks (LRM/RLM, embeddings, isolates) that Hebrew/Arabic text copied from
     Word or a browser is full of. They are invisible on screen but break exact matching
     and BM25 tokens ("‏חופשה" != "חופשה").
  3. Maps exotic spaces (NBSP, thin space...) to a normal space, tabs to a space, CRLF to LF.
  4. Hebrew: geresh/gershayim (U+05F3/U+05F4) to ASCII ' and ", maqaf (U+05BE) to "-",
     and optionally strips niqqud (vowel points), which almost no query contains.
  5. Whitespace: collapses runs of spaces inside a line, strips line ends, keeps at most
     one blank line between paragraphs (paragraph breaks are structure: keep them).

Header/footer removal and de-hyphenation are PDF-specific and live in the PDF loader,
using the helpers below (repeated_lines, dehyphenate).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Iterable

INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"
                                   "‎‏‪‫‬‭‮"
                                   "⁦⁧⁨⁩؜"), None)
SPACES = {ord(c): " " for c in "         "
                                "     　\t"}
HEBREW_PUNCT = {0x05F3: "'", 0x05F4: '"', 0x05BE: "-"}
NIQQUD_RE = re.compile(r"[֑-ׇֽֿׁׂׅׄ]")
HEBREW_RE = re.compile(r"[א-ת]")


def normalize(text: str, *, strip_niqqud: bool = True) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(INVISIBLE).translate(SPACES).translate(HEBREW_PUNCT)
    if strip_niqqud:
        text = NIQQUD_RE.sub("", text)
    lines = []
    for line in text.split("\n"):
        m = re.match(r" *", line)
        indent = m.group(0) if m else ""
        body = re.sub(r" {2,}", " ", line[len(indent):]).rstrip()
        lines.append((indent + body) if body else "")
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def collapse_ws(text: str) -> str:
    """normalize() and then one space for every whitespace run: the form used to compare a
    quote with a chunk (PDF line breaks must not decide whether a quote "exists")."""
    return " ".join(normalize(text).split())


def hebrew_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if HEBREW_RE.match(c)) / len(letters)


def guess_language(text: str) -> str:
    return "he" if hebrew_ratio(text) > 0.3 else "en"


def invisible_report(text: str) -> Counter:
    """Count the invisible/bidi/odd-space characters in text, by code point name."""
    c: Counter = Counter()
    for ch in text:
        if ord(ch) in INVISIBLE or (ord(ch) in SPACES and ch != "\t"):
            c[unicodedata.name(ch, hex(ord(ch)))] += 1
    return c


# ---------------------------------------------------------------- PDF helpers

DIGITS_RE = re.compile(r"\d+")
PAGE_NO_RE = re.compile(r"^\s*(page\s*)?\d+(\s*(of|/)\s*\d+)?\s*$", re.I)


def _line_key(line: str) -> str:
    return DIGITS_RE.sub("#", " ".join(line.split())).lower()


def repeated_lines(pages: list[str], *, edge: int = 4, min_share: float = 0.6) -> set[str]:
    """Header/footer lines: lines that appear (digits ignored, so "Page 1" == "Page 2") on at
    least `min_share` of the pages, within the first or last `edge` lines of the page.
    Needs at least 2 pages; a one-page PDF only gets bare page numbers removed."""
    if len(pages) < 2:
        return set()
    seen: Counter = Counter()
    for page in pages:
        lines = [ln for ln in page.split("\n") if ln.strip()]
        keys = {_line_key(ln) for ln in lines[:edge] + lines[-edge:]}
        seen.update(keys)
    need = max(2, int(round(min_share * len(pages))))
    return {k for k, n in seen.items() if n >= need}


def strip_lines(page: str, keys: set[str], *, edge: int = 4) -> tuple[str, list[str]]:
    """Remove header/footer lines (by key) and bare page numbers near the page edges.
    Returns (page_text, removed_lines)."""
    lines = page.split("\n")
    nonempty = [i for i, ln in enumerate(lines) if ln.strip()]
    edges = set(nonempty[:edge] + nonempty[-edge:])
    kept, removed = [], []
    for i, ln in enumerate(lines):
        if i in edges and (_line_key(ln) in keys or PAGE_NO_RE.match(ln)):
            removed.append(ln.strip())
        else:
            kept.append(ln)
    return "\n".join(kept), removed


def dehyphenate(text: str) -> str:
    """'infor-\\nmation' -> 'information' (only lowercase on both sides, so 'flow-\\nAPI'
    and real hyphenated words at a line end such as 'per-\\nseat' are a known risk)."""
    return re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)


def join_nonempty(parts: Iterable[str], sep: str = "\n\n") -> str:
    return sep.join(p.strip() for p in parts if p and p.strip())
