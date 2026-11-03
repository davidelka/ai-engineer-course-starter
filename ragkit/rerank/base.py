"""The Reranker contract, and the retriever that wraps one (lesson 12).

    rerank(query, hits, top_n=None) -> list[Hit]

A first-stage retriever (BM25, dense, hybrid) scores the query and each chunk SEPARATELY, so
it can precompute everything and search millions of chunks in milliseconds. A reranker reads
the query and one candidate TOGETHER (a cross-encoder, a hosted rerank API, or an LLM) and
can therefore notice that "may NOT be carried over" contradicts the question, or that the
chunk answers a different product's SLA. That costs a model pass per candidate, so it only
runs on the first stage's top 20-100: "retrieve wide, rerank narrow".

BaseReranker implements rerank() once: subclasses only provide score(query, texts). The
reranker sees chunk.context_text() (title + section path + text), like the indexes did.
Ties keep the first stage's order (a stable sort). Each Hit keeps its earlier scores and gains
scores["rerank"]; stats has the call count, latency and cost of the last call.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Optional, Protocol, Sequence, runtime_checkable

from ..retrieval.base import Retriever, Where
from ..types import Hit


@runtime_checkable
class Reranker(Protocol):
    name: str

    def rerank(self, query: str, hits: Sequence[Hit], top_n: Optional[int] = None) -> list[Hit]: ...


@dataclass
class RerankStats:
    calls: int = 0                 # model/API calls in the last rerank()
    pairs: int = 0                 # (query, passage) pairs scored
    latency_s: float = 0.0
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated: bool = False        # cost estimated (offline replay, or price not verified)
    extra: dict = field(default_factory=dict)


class BaseReranker:
    name = "reranker"
    max_chars = 2000               # passages are cut to this many characters before scoring

    def __init__(self) -> None:
        self.stats = RerankStats()
        self.total_cost = 0.0

    def passage(self, hit: Hit) -> str:
        return hit.chunk.context_text()[: self.max_chars]

    def score(self, query: str, texts: list[str]) -> list[float]:  # pragma: no cover - abstract
        raise NotImplementedError

    def rerank(self, query: str, hits: Sequence[Hit], top_n: Optional[int] = None) -> list[Hit]:
        hits = list(hits)
        self.stats = RerankStats()
        if not hits:
            return []
        t0 = time.perf_counter()
        scores = self.score(query, [self.passage(h) for h in hits])
        self.stats.latency_s = time.perf_counter() - t0
        self.stats.pairs = len(hits)
        self.total_cost += self.stats.cost_usd
        if len(scores) != len(hits):
            raise RuntimeError(f"{self.name}: {len(scores)} scores for {len(hits)} passages")
        order = sorted(range(len(hits)), key=lambda i: -scores[i])       # stable: ties keep order
        out = []
        for new_rank, i in enumerate(order[: top_n or len(order)], start=1):
            h = hits[i]
            sc = dict(h.scores)
            sc["rerank"] = float(scores[i])
            sc.setdefault("first_stage_rank", float(h.rank or i + 1))
            out.append(replace(h, score=float(scores[i]), rank=new_rank, scores=sc,
                               retriever=f"{h.retriever}>{self.name}" if h.retriever else self.name))
        return out


class RerankingRetriever:
    """First stage fetches fetch_k candidates, the reranker keeps the best k."""

    def __init__(self, base: Retriever, reranker: Reranker, *, fetch_k: int = 30, name: Optional[str] = None):
        self.base, self.reranker, self.fetch_k = base, reranker, fetch_k
        self.name = name or f"{getattr(base, 'name', 'base')}+rerank:{reranker.name}@{fetch_k}"
        self.last_timing: dict[str, float] = {}

    def search(self, query: str, k: int = 5, where: Where = None) -> list[Hit]:
        """Rerank the first fetch_k candidates. If k > fetch_k, the rest follow in first-stage
        order (an evaluation that reads the top 10 still sees what the reranker did NOT see)."""
        t0 = time.perf_counter()
        cands = self.base.search(query, k=max(k, self.fetch_k), where=where)
        t_first = (time.perf_counter() - t0) * 1000
        head, tail = cands[: self.fetch_k], cands[self.fetch_k:]
        out = self.reranker.rerank(query, head, top_n=min(k, len(head)))
        if len(out) < k and tail:
            out += [replace(h, rank=len(out) + i, scores=dict(h.scores))
                    for i, h in enumerate(tail[: k - len(out)], start=1)]
        st = getattr(self.reranker, "stats", None)
        self.last_timing = {**getattr(self.base, "last_timing", {}), "first_stage": t_first,
                            "rerank": (st.latency_s * 1000) if st else 0.0}
        self.last_cost = st.cost_usd if st else 0.0
        return out


__all__ = ["Reranker", "BaseReranker", "RerankStats", "RerankingRetriever"]
