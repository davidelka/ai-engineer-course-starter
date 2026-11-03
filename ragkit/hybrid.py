"""Hybrid retrieval (lesson 12): run several retrievers, fuse their rankings into one.

    from ragkit.hybrid import HybridRetriever
    hybrid = HybridRetriever({"bm25": bm25, "dense": dense})              # RRF, k=60
    hybrid = HybridRetriever({"bm25": bm25, "dense": dense}, method="weighted",
                             weights=[0.3, 0.7], normalize="minmax")
    hits = hybrid.search("What is the per diem in Berlin?", k=5)
    hits[0].scores   # {"bm25": 12.1, "vector": 0.83, "rank:bm25": 1, "rank:dense": 3, "rrf": 0.0323}

Why it works: BM25 and dense retrieval fail on DIFFERENT questions. BM25 needs the exact
word (it finds "il-central-1", "FIDO2", "$85" and misses "time off" vs "vacation", and every
question whose source is in the other language). Dense finds paraphrases and translations and
blurs identifiers, numbers and negation. Fusion keeps a chunk that either one ranks high, and
pushes up chunks that BOTH rank high.

Each child is asked for exactly `fetch_k` results, whatever k is (more than k: a chunk ranked
12th by BM25 and 2nd by dense should survive; and a fixed depth means asking for k=5 or k=30
gives the same order, so a wrapper that over-fetches does not change the fusion). Every Hit keeps every child's own score (bm25, vector...), its rank
in each child ("rank:<name>"), and the fused score ("rrf" or "fused"), so a debugger can show
why a chunk landed where it did. `last_timing` holds milliseconds per child and for the fusion.

HybridRetriever is also an Index (add/remove go to every child that has them), so it drops into
IngestPipeline(index=...) and rag.answer(...) unchanged.
"""

from __future__ import annotations

import time
from typing import Iterable, Mapping, Optional, Sequence, Union

from .fusion import rrf, weighted_fusion
from .retrieval.base import Retriever, Where
from .types import Chunk, Hit


def fuse_hits(hit_lists: Mapping[str, Sequence[Hit]], *, method: str = "rrf", k_rrf: float = 60.0,
              weights: Optional[Sequence[float]] = None, normalize: str = "minmax",
              name: str = "hybrid") -> list[Hit]:
    """Fuse named lists of Hits (by chunk id) into one best-first list of NEW Hits."""
    names = list(hit_lists)
    chunks: dict[str, Chunk] = {}
    scores: dict[str, dict[str, float]] = {}
    for n in names:
        for r, h in enumerate(hit_lists[n], start=1):
            cid = h.chunk.id
            chunks.setdefault(cid, h.chunk)
            s = scores.setdefault(cid, {})
            for key, v in h.scores.items():
                s.setdefault(key, v)
            s.setdefault(f"rank:{n}", float(r))
    if method == "rrf":
        fused = rrf([[h.chunk.id for h in hit_lists[n]] for n in names], k=k_rrf, weights=weights)
        key = "rrf"
    elif method == "weighted":
        fused = weighted_fusion([{h.chunk.id: h.score for h in hit_lists[n]} for n in names],
                                weights=weights, normalize=normalize)
        key = "fused"
    else:
        raise ValueError("method must be 'rrf' or 'weighted'")
    out = []
    for i, (cid, sc) in enumerate(fused, start=1):
        s = dict(scores[cid])
        s[key] = sc
        out.append(Hit(chunk=chunks[cid], score=sc, rank=i, scores=s, retriever=name))
    return out


class HybridRetriever:
    def __init__(self, retrievers: Union[Mapping[str, Retriever], Sequence[Retriever]], *,
                 method: str = "rrf", k_rrf: float = 60.0, weights: Optional[Sequence[float]] = None,
                 normalize: str = "minmax", fetch_k: int = 50, name: Optional[str] = None):
        if not isinstance(retrievers, Mapping):
            retrievers = {getattr(r, "name", f"r{i}"): r for i, r in enumerate(retrievers)}
        if len(retrievers) < 1:
            raise ValueError("need at least one retriever")
        self.retrievers = dict(retrievers)
        self.method, self.k_rrf, self.weights, self.normalize = method, k_rrf, weights, normalize
        self.fetch_k = fetch_k
        self.name = name or f"{method}(" + "+".join(self.retrievers) + ")"
        self.last_timing: dict[str, float] = {}

    # -- Index protocol (delegated)
    def add(self, chunks: Iterable[Chunk]) -> None:
        chunks = list(chunks)
        for r in self.retrievers.values():
            if hasattr(r, "add"):
                r.add(chunks)

    def remove(self, doc_id: str) -> int:
        return max([r.remove(doc_id) for r in self.retrievers.values() if hasattr(r, "remove")] or [0])

    def search(self, query: str, k: int = 5, where: Where = None) -> list[Hit]:
        timing: dict[str, float] = {}
        lists: dict[str, list[Hit]] = {}
        for n, r in self.retrievers.items():
            t0 = time.perf_counter()
            lists[n] = r.search(query, k=self.fetch_k, where=where)
            timing[n] = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        out = fuse_hits(lists, method=self.method, k_rrf=self.k_rrf, weights=self.weights,
                        normalize=self.normalize, name=self.name)[:k]
        timing["fusion"] = (time.perf_counter() - t0) * 1000
        self.last_timing = timing
        return out


__all__ = ["HybridRetriever", "fuse_hits"]
