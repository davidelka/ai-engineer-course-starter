"""OverlapReranker: a free, deterministic, offline stand-in for a reranker. NOT a model.

score(query, passage) = (sum of weights of the query terms the passage contains)
                        / (sum of weights of all query terms)
weight(term) = ln(1 + n / (1 + df)), df counted over the n candidates being reranked, so a
term that every candidate contains (the product name) counts little and a rare one counts a
lot. Terms come from ragkit's analyzer (Hebrew prefix variants included), and a passage that
contains two query terms next to each other in the query's order gets a small bonus.

It is lexical: it cannot read meaning, negation or the other language, so it will not do
what a cross-encoder does. It exists so the reranking code path, the tests and the ablation
run anywhere without a download. Never judge reranking by its numbers; every script says so.
"""

from __future__ import annotations

import math

from ..retrieval.analyzer import analyze
from .base import BaseReranker


class OverlapReranker(BaseReranker):
    name = "fake-overlap"

    def __init__(self, bigram_bonus: float = 0.1):
        super().__init__()
        self.bigram_bonus = bigram_bonus

    def score(self, query: str, texts: list[str]) -> list[float]:
        q_terms = list(dict.fromkeys(t for t in analyze(query, hebrew_prefixes=False)))
        if not q_terms:
            return [0.0] * len(texts)
        docs = [analyze(t) for t in texts]
        sets = [set(d) for d in docs]
        n = len(texts)
        weight = {t: math.log(1 + n / (1 + sum(t in s for s in sets))) for t in q_terms}
        total = sum(weight.values()) or 1.0
        pairs = list(zip(q_terms, q_terms[1:]))
        out = []
        for d, s in zip(docs, sets):
            cov = sum(w for t, w in weight.items() if t in s) / total
            if pairs:
                bigrams = set(zip(d, d[1:]))
                cov += self.bigram_bonus * sum(p in bigrams for p in pairs) / len(pairs)
            out.append(round(cov, 6))
        self.stats.calls = 0
        return out


__all__ = ["OverlapReranker"]
