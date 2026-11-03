"""Ranking metrics for retrieval (lesson 10), at DOCUMENT level, on the golden set.

A retriever returns a ranked list of chunks; a golden question lists the relevant documents
(`source_ids`). We first turn the chunk ranking into a document ranking: keep each document's
first (best) position and drop its later chunks. Then:

- recall@k  = |relevant docs among the first k ranked docs| / |relevant docs|
              (multi-hop questions have 2-3 relevant docs: finding one of three is 1/3)
- hit@k     = 1 if at least one relevant doc is in the first k, else 0
- RR        = 1 / (rank of the first relevant doc), 0 if none is ranked
- MRR       = mean of RR over questions (we cut the ranking at k, i.e. MRR@k)

Documents rather than chunks because the golden set labels documents, and a document that
appears twice in the top 5 should not count twice. Questions without sources (unanswerable)
are skipped: recall is undefined for them.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from .retrieval.base import Retriever


def dedupe(ids: Iterable[str]) -> list[str]:
    """Keep the first occurrence of each id, preserving order."""
    return list(dict.fromkeys(ids))


def recall_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    rel = set(relevant)
    if not rel:
        raise ValueError("recall is undefined without relevant ids")
    top = dedupe(ranked)[:k]
    return len(rel.intersection(top)) / len(rel)


def hit_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    rel = set(relevant)
    return float(any(d in rel for d in dedupe(ranked)[:k]))


def reciprocal_rank(ranked: Sequence[str], relevant: Iterable[str], k: Optional[int] = None) -> float:
    rel = set(relevant)
    for i, d in enumerate(dedupe(ranked)[:k] if k else dedupe(ranked), start=1):
        if d in rel:
            return 1.0 / i
    return 0.0


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


@dataclass
class QueryResult:
    qid: str
    qtype: str
    question: str
    relevant: list[str]
    ranked_docs: list[str]            # deduplicated document ranking
    groups: list[str] = field(default_factory=list)   # extra groupings, e.g. "cross-lingual"

    def recall(self, k: int) -> float:
        return recall_at_k(self.ranked_docs, self.relevant, k)

    def hit(self, k: int) -> float:
        return hit_at_k(self.ranked_docs, self.relevant, k)

    def rr(self, k: Optional[int] = None) -> float:
        return reciprocal_rank(self.ranked_docs, self.relevant, k)


def is_hebrew(text: str) -> bool:
    return any("֐" <= ch <= "׿" for ch in text)


def run_queries(retriever: Retriever, qa: list[dict], depth: int = 10) -> list[QueryResult]:
    """Search every answerable golden question once, keep the top `depth` document ranking.
    Questions tagged "cross-lingual" in the golden set (question and source in different
    languages) also get the group "cross-lingual"."""
    out = []
    for q in qa:
        if not q.get("source_ids"):
            continue
        # over-fetch chunks: several chunks of one document collapse into one rank
        hits = retriever.search(q["question"], k=depth * 3)
        ranked = dedupe(h.chunk.doc_id for h in hits)[:depth]
        groups = ["cross-lingual"] if "cross-lingual" in (q.get("tags") or []) else []
        out.append(QueryResult(q["id"], q.get("type", ""), q["question"], list(q["source_ids"]), ranked, groups))
    return out


def summarize(results: list[QueryResult], ks: Sequence[int] = (1, 5, 10), mrr_k: int = 10,
              by: str = "type") -> dict[str, dict[str, float]]:
    """{group: {"n", "recall@k"..., "hit@k"..., "mrr"}} with an "ALL" row. by="type" groups by
    question type and also adds the extra groups (cross-lingual)."""
    buckets: dict[str, list[QueryResult]] = defaultdict(list)
    for r in results:
        buckets["ALL"].append(r)
        if by == "type":
            buckets[r.qtype].append(r)
            for g in r.groups:
                buckets[g].append(r)
    table = {}
    for name, rs in buckets.items():
        row = {"n": float(len(rs))}
        for k in ks:
            row[f"recall@{k}"] = mean([r.recall(k) for r in rs])
            row[f"hit@{k}"] = mean([r.hit(k) for r in rs])
        row["mrr"] = mean([r.rr(mrr_k) for r in rs])
        table[name] = row
    order = sorted(table, key=lambda n: (n == "ALL", n == "cross-lingual", n))
    return {n: table[n] for n in order}


def format_summary(table: dict[str, dict[str, float]], cols: Sequence[str] = ("recall@1", "recall@5", "recall@10", "mrr")) -> str:
    lines = [f"{'group':16s} {'n':>3s}  " + " ".join(f"{c:>9s}" for c in cols)]
    for name, row in table.items():
        lines.append(f"{name:16s} {int(row['n']):3d}  " + " ".join(f"{row[c]:9.3f}" for c in cols))
    return "\n".join(lines)
