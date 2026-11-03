"""Snippets with highlights: show WHY a file matched.

The terms are matched the way BM25 matched them (ragkit's analyzer, including Hebrew prefix
variants), so "בערבות" in the text is highlighted for the query "ערבות". A dense-only hit may
share no word with the query at all: then the snippet is the start of the chunk, and the UI
labels it "semantic match" (the user should know that nothing literal matched).
"""

from __future__ import annotations

import re
from html import escape

from ragkit.retrieval.analyzer import analyze, hebrew_variants

WORD = re.compile(r"\w+", re.U)


def query_terms(query: str) -> set[str]:
    return set(analyze(query))


def word_matches(word: str, terms: set[str]) -> bool:
    w = word.lower()
    return w in terms or any(v in terms for v in hebrew_variants(w))


def make_snippet(text: str, query: str, width: int = 240) -> str:
    """HTML: an escaped window of `text` around the densest run of matches, <mark> on matches."""
    text = " ".join(text.split())
    terms = query_terms(query)
    spans = [(m.start(), m.end()) for m in WORD.finditer(text) if word_matches(m.group(0), terms)] if terms else []
    if spans:
        best, best_n = spans[0][0], 0
        for s, _ in spans:
            n = sum(1 for a, _ in spans if s <= a < s + width)
            if n > best_n:
                best, best_n = s, n
        start = max(0, best - width // 4)
    else:
        start = 0
    end = min(len(text), start + width)
    if start > 0:
        sp = text.find(" ", start)
        start = sp + 1 if 0 <= sp < start + 20 else start
    out, pos = [], start
    for a, b in spans:
        if a < start or b > end:
            continue
        out.append(escape(text[pos:a]))
        out.append("<mark>" + escape(text[a:b]) + "</mark>")
        pos = b
    out.append(escape(text[pos:end]))
    return ("… " if start > 0 else "") + "".join(out) + (" …" if end < len(text) else "")


def has_literal_match(text: str, query: str) -> bool:
    terms = query_terms(query)
    return any(word_matches(m.group(0), terms) for m in WORD.finditer(text))
