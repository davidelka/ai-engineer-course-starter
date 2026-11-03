"""Measure a retrieval pipeline stage by stage (lesson 12): quality, latency and cost.

    from ragkit.ablation import evaluate_stage, format_stage
    rep = evaluate_stage("bm25+dense (RRF)", hybrid, qa)
    print(format_stage(rep))

An ablation adds (or removes) ONE stage at a time on the SAME chunks and the SAME golden
questions, so each difference has one cause. For every stage we record, per question type
and for the cross-lingual group: recall@5 and MRR@10 (ragkit.metrics, document level),
stale@5 for version_conflict questions (ragkit.versions), the wall-clock latency of each
search (p50 and p95), and the money spent per query by LLM or API stages.

Latency of a stage whose LLM answer came from a cache counts the time of the ORIGINAL call
(a production request would pay it); offline replay calls take ~0 ms and are flagged, so
never read offline latency of an LLM stage as real.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Optional, Sequence

from . import metrics as M
from .retrieval.base import Retriever
from .versions import stale_at_k


def _walk(r, seen=None):
    """Yield r and every retriever nested in it (base, retrievers...)."""
    seen = seen if seen is not None else set()
    if r is None or id(r) in seen:
        return
    seen.add(id(r))
    yield r
    for attr in ("base",):
        yield from _walk(getattr(r, attr, None), seen)
    for child in (getattr(r, "retrievers", None) or {}).values():
        yield from _walk(child, seen)


def last_cost_and_extra_ms(r) -> tuple[float, float]:
    """(USD spent by the last search, ms to add for answers served from a cache)."""
    cost, extra = 0.0, 0.0
    for x in _walk(r):
        cost += float(getattr(x, "last_cost", 0.0) or 0.0)
        t = getattr(x, "last_timing", None) or {}
        if t.get("rewrite_cached"):
            extra += float(t.get("rewrite_llm", 0.0))
    return cost, extra


def uses_replay(r) -> bool:
    for x in _walk(r):
        for obj in (getattr(x, "rewriter", None), getattr(x, "reranker", None)):
            llm = getattr(obj, "llm", None)
            if llm is not None and getattr(llm, "api_key", "") == "replay":
                return True
    return False


@dataclass
class StageReport:
    name: str
    table: dict[str, dict[str, float]]
    stale5: float                         # fraction of version_conflict questions with a stale doc in top 5
    latency_ms: list[float] = field(default_factory=list)
    cost_usd: list[float] = field(default_factory=list)
    replay: bool = False
    results: list = field(default_factory=list)

    @property
    def p50(self) -> float:
        return statistics.median(self.latency_ms) if self.latency_ms else 0.0

    @property
    def p95(self) -> float:
        if not self.latency_ms:
            return 0.0
        xs = sorted(self.latency_ms)
        return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]

    @property
    def cost_per_query(self) -> float:
        return statistics.fmean(self.cost_usd) if self.cost_usd else 0.0

    def get(self, group: str, metric: str) -> float:
        return self.table.get(group, {}).get(metric, float("nan"))

    def to_dict(self) -> dict:
        return {"name": self.name, "table": self.table, "stale5": self.stale5, "p50_ms": self.p50,
                "p95_ms": self.p95, "cost_per_query": self.cost_per_query,
                "cost_total": sum(self.cost_usd), "replay": self.replay}


def evaluate_stage(name: str, retriever: Retriever, qa: list[dict], depth: int = 10) -> StageReport:
    """Run every answerable golden question once through `retriever`, timing each search."""
    results, lat, cost = [], [], []
    vc = {q["id"]: q for q in qa if q.get("type") == "version_conflict"}
    stale = []
    for q in qa:
        if not q.get("source_ids"):
            continue
        t0 = time.perf_counter()
        hits = retriever.search(q["question"], k=depth * 3)
        ms = (time.perf_counter() - t0) * 1000
        c, extra = last_cost_and_extra_ms(retriever)
        lat.append(ms + extra)
        cost.append(c)
        ranked = M.dedupe(h.chunk.doc_id for h in hits)[:depth]
        groups = ["cross-lingual"] if "cross-lingual" in (q.get("tags") or []) else []
        results.append(M.QueryResult(q["id"], q.get("type", ""), q["question"], list(q["source_ids"]), ranked, groups))
        if q["id"] in vc:
            stale.append(stale_at_k(ranked, q, 5))
    return StageReport(name, M.summarize(results), M.mean(stale), lat, cost, uses_replay(retriever), results)


GROUPS = ("ALL", "multi_hop", "version_conflict", "hebrew", "cross-lingual")


def format_stage(rep: StageReport, groups: Sequence[str] = GROUPS, prev: Optional[StageReport] = None) -> str:
    """One stage as a short list (no tables): quality per group, then latency and cost."""
    def delta(g, m):
        if prev is None:
            return ""
        d = rep.get(g, m) - prev.get(g, m)
        return f" ({d:+.3f})" if abs(d) >= 0.0005 else " (=)"
    lines = [f"- {rep.name}"]
    for g in groups:
        if g in rep.table:
            n = int(rep.table[g]["n"])
            lines.append(f"    {g} (n={n}): recall@5 {rep.get(g, 'recall@5'):.3f}{delta(g, 'recall@5')}, "
                         f"MRR {rep.get(g, 'mrr'):.3f}{delta(g, 'mrr')}")
    if "version_conflict" in rep.table:
        n_vc = int(rep.table["version_conflict"]["n"])
        lines.append(f"    version_conflict with a stale doc in the top 5: {round(rep.stale5 * n_vc)}/{n_vc}")
    lat = f"latency p50 {rep.p50:.1f} ms, p95 {rep.p95:.1f} ms"
    if rep.replay:
        lat += "  [LLM calls replayed offline: a live call adds its own latency; measure it live]"
    lines.append(f"    {lat}")
    lines.append(f"    cost ${rep.cost_per_query:.5f} per query, ${sum(rep.cost_usd):.4f} for {len(rep.cost_usd)} questions"
                 + ("  [estimated: replay]" if rep.replay and sum(rep.cost_usd) > 0 else ""))
    return "\n".join(x for x in lines if x)


__all__ = ["StageReport", "evaluate_stage", "format_stage", "last_cost_and_extra_ms", "uses_replay", "GROUPS"]
