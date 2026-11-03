"""Version-aware retrieval (lesson 12): stop citing the superseded policy.

The Acme corpus keeps old versions next to new ones (hr-vacation-2024 next to hr-vacation-2026,
fin-travel-2025 next to fin-travel-2026...). Retrieval that is "good" finds BOTH: they share
almost every word and almost every embedding direction. Lesson 9 measured the result: 5 of the
11 version_conflict answers cited the superseded document.

The newer document says which one it replaces, in its metadata (`supersedes: hr-vacation-2024`;
a string or a list). The old one is not marked at all, as in a real company. ragkit copies the
field onto every chunk, so it is available on each Hit.

Three policies, from safest to most aggressive:

- drop_superseded(hits)                       mode "retrieved": drop a chunk only when a NEWER
      version of its document is ALSO in the result list. Safe: if only the old version was
      found, it stays (better an old answer with its date than no answer).
- drop_superseded(hits, superseded_by=MAP)    mode "corpus": drop any document that has a
      successor anywhere in the corpus (MAP = supersedes_map(all_chunks)). Equivalent to a
      pre-filter `where`. It also hides the old version from a question that ASKS about it
      ("what was the carry-over rule in 2024?").
- boost_recent(hits, weight)                  add weight * recency (effective_date, ranked within
      the list) to the score. Needs no `supersedes` links, so it also helps meeting notes that
      contradict each other; but it prefers ANY newer document, relevant or not.

Not every conflict has a `supersedes` link: an all-hands note that was corrected later (q004),
a meeting "decision" that was reversed (q005), a proposal that was never adopted (q011). Those
need the answer step to compare dates, or the documents to carry better metadata. Measure which
questions the filter fixes and which it cannot touch (versions_eval.py).

stale_at_k() measures the failure directly: the golden set tags each version_conflict question
with `stale:<doc_id>`, the superseded document(s) that could mislead the answer.
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Iterable, Mapping, Optional, Sequence

from .retrieval.base import Retriever, Where
from .types import Chunk, Hit


def _as_list(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v]


def supersedes_map(chunks: Iterable[Chunk]) -> dict[str, set[str]]:
    """old doc id -> {doc ids that directly supersede it}, from the chunks' `supersedes` meta."""
    out: dict[str, set[str]] = {}
    for c in chunks:
        for old in _as_list(c.meta.get("supersedes")):
            if old != c.doc_id:
                out.setdefault(old, set()).add(c.doc_id)
    return out


def _successors(doc: str, by: Mapping[str, set[str]]) -> set[str]:
    """Every document that supersedes `doc`, directly or through a chain (cycle-safe)."""
    seen: set[str] = set()
    todo = list(by.get(doc, ()))
    while todo:
        d = todo.pop()
        if d in seen or d == doc:
            continue
        seen.add(d)
        todo.extend(by.get(d, ()))
    return seen


def _rerank(hits: Sequence[Hit]) -> list[Hit]:
    return [replace(h, rank=i, scores=dict(h.scores)) for i, h in enumerate(hits, start=1)]


def drop_superseded(hits: Sequence[Hit], superseded_by: Optional[Mapping[str, Iterable[str]]] = None) -> list[Hit]:
    """Remove chunks of documents that are superseded (see the module docstring).

    Without `superseded_by` ("retrieved" mode) the links come from the hits themselves, and a
    chunk is dropped only if one of its document's successors (direct or via a chain) is
    present in `hits`. With `superseded_by` ("corpus" mode) a chunk is dropped if its document
    has any successor in the map. Order is kept; ranks are renumbered 1..n; inputs untouched.
    """
    if superseded_by is not None:
        by = {k: set(v) for k, v in superseded_by.items()}
        return _rerank([h for h in hits if not _successors(h.chunk.doc_id, by)])
    by = supersedes_map(h.chunk for h in hits)
    present = {h.chunk.doc_id for h in hits}
    return _rerank([h for h in hits if not (_successors(h.chunk.doc_id, by) & present)])


def boost_recent(hits: Sequence[Hit], weight: float = 0.1, *, score_key: Optional[str] = None) -> list[Hit]:
    """New score = score / max score + weight * recency, re-sorted. recency is the position of
    the chunk's effective_date among the distinct dates in this list, scaled to 0..1 (newest 1).
    Dividing by the max (not min-max) keeps a close second close: with min-max the second of two
    hits would drop to 0 and any boost would look huge. Dates are ISO strings (YYYY-MM-DD), so
    they compare as text; a missing date counts as the oldest."""
    if not hits:
        return []
    base = [h.scores.get(score_key, h.score) if score_key else h.score for h in hits]
    hi = max(base)
    dates = sorted({h.chunk.effective_date for h in hits if h.chunk.effective_date})
    order = {d: i for i, d in enumerate(dates)}

    def rec(h: Hit) -> float:
        d = h.chunk.effective_date
        if not d or len(dates) < 2:
            return 0.0
        return order[d] / (len(dates) - 1)

    rescored = []
    for h, b in zip(hits, base):
        s = (b / hi if hi > 0 else 1.0) + weight * rec(h)
        rescored.append((s, h))
    rescored.sort(key=lambda x: (-x[0], x[1].rank))
    out = []
    for i, (s, h) in enumerate(rescored, start=1):
        sc = dict(h.scores)
        sc["recency"] = s
        out.append(replace(h, score=s, rank=i, scores=sc))
    return out


class VersionAwareRetriever:
    """Wraps a retriever: over-fetch, apply a version policy, keep k.

    mode: "retrieved" (default) | "corpus" (needs superseded_by) | "recent" (boost_recent)
    """

    def __init__(self, base: Retriever, *, mode: str = "retrieved",
                 superseded_by: Optional[Mapping[str, Iterable[str]]] = None,
                 recency_weight: float = 0.1, fetch_k: int = 50, name: Optional[str] = None):
        if mode == "corpus" and superseded_by is None:
            raise ValueError("mode='corpus' needs superseded_by=supersedes_map(all_chunks)")
        if mode not in ("retrieved", "corpus", "recent"):
            raise ValueError("mode must be retrieved | corpus | recent")
        self.base, self.mode, self.superseded_by = base, mode, superseded_by
        self.recency_weight, self.fetch_k = recency_weight, fetch_k
        self.name = name or f"{getattr(base, 'name', 'base')}+versions:{mode}"
        self.last_timing: dict[str, float] = {}

    def search(self, query: str, k: int = 5, where: Where = None) -> list[Hit]:
        hits = self.base.search(query, k=max(k, self.fetch_k), where=where)
        t0 = time.perf_counter()
        if self.mode == "recent":
            out = boost_recent(hits, self.recency_weight)
        else:
            out = drop_superseded(hits, self.superseded_by if self.mode == "corpus" else None)
        self.last_timing = {**getattr(self.base, "last_timing", {}), "versions": (time.perf_counter() - t0) * 1000}
        for h in out:
            h.retriever = self.name
        return out[:k]


def stale_docs(q: dict) -> set[str]:
    """The superseded documents a golden question warns about (tags 'stale:<doc_id>')."""
    return {t.split(":", 1)[1] for t in (q.get("tags") or []) if t.startswith("stale:")}


def stale_at_k(ranked_docs: Sequence[str], q: dict, k: int = 5) -> float:
    """1.0 if any stale document of question q is among the first k (deduplicated) docs."""
    stale = stale_docs(q)
    top = list(dict.fromkeys(ranked_docs))[:k]
    return float(any(d in stale for d in top))


__all__ = ["supersedes_map", "drop_superseded", "boost_recent", "VersionAwareRetriever",
           "stale_docs", "stale_at_k"]
