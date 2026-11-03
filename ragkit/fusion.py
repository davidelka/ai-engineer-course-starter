"""Rank fusion (lesson 12): merge several ranked lists into one.

Two families, and why both exist:

1. Reciprocal Rank Fusion (Cormack, Clarke and Buettcher, SIGIR 2009). Uses only POSITIONS:

       rrf(d) = sum over lists i that contain d of   w_i / (k + rank_i(d))       (rank is 1-based)

   A document missing from a list contributes 0 for that list. k (60 in the paper, and the
   default in Elasticsearch, OpenSearch, Azure AI Search...) flattens the curve: with k=60,
   rank 1 is worth 1/61 = 0.0164 and rank 10 is worth 1/70 = 0.0143, so being found by BOTH
   retrievers beats being first in only one. With k=0 rank 1 is worth 1.0 and rank 2 only
   0.5: the fusion becomes "whoever was first somewhere". No score normalization is needed,
   which is the whole point: BM25 scores (0..30, unbounded) and cosine (0.7..0.9 for e5)
   live on unrelated scales.

2. Weighted score fusion ("convex combination", Weaviate's relativeScoreFusion, alpha in
   many vector DBs). Keeps the score MAGNITUDES, so "far ahead" counts more than "slightly
   ahead". But the scales must be made comparable first, and every normalization has a trap:
     - min-max maps each list to [0, 1]. The best item always gets 1.0, even when it is
       bad in absolute terms (a list of five irrelevant chunks still has a 1.0). One outlier
       squashes everybody else towards 0. The LAST item of a list gets 0.0, exactly like an
       item the retriever did not return at all.
     - z-score is less sensitive to one outlier but still depends on how many items you
       fetched (fetch 10 or 50 and the mean moves).
   The weights only mean something AFTER normalization, and they need tuning per corpus.

Ties are broken deterministically: higher score first, then the best (lowest) rank the item
reached in any input list, then the id. Sums use math.fsum, which is exactly rounded, so the
result does not depend on the order of the input lists.
"""

from __future__ import annotations

import math
import statistics
from typing import Hashable, Mapping, Optional, Sequence

Id = Hashable


def _positions(ranking: Sequence[Id]) -> dict[Id, int]:
    """id -> 1-based rank, keeping the FIRST occurrence when an id repeats."""
    pos: dict[Id, int] = {}
    for i, d in enumerate(ranking, start=1):
        pos.setdefault(d, i)
    return pos


def rrf(rankings: Sequence[Sequence[Id]], k: float = 60.0,
        weights: Optional[Sequence[float]] = None) -> list[tuple[Id, float]]:
    """Reciprocal Rank Fusion of best-first id lists. Returns [(id, score)] best first.

    rrf([["a", "b", "c"], ["c", "a"]], k=60)
      a: 1/61 + 1/62 = 0.03252     c: 1/63 + 1/61 = 0.03227     b: 1/62 = 0.01613
    """
    if k < 0:
        raise ValueError("k must be >= 0")
    weights = list(weights) if weights is not None else [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError("one weight per ranking")
    terms: dict[Id, list[float]] = {}
    best: dict[Id, int] = {}
    for ranking, w in zip(rankings, weights):
        for d, r in _positions(ranking).items():
            terms.setdefault(d, []).append(w / (k + r))
            best[d] = min(best.get(d, r), r)
    scores = {d: math.fsum(ts) for d, ts in terms.items()}
    return sorted(scores.items(), key=lambda x: (-x[1], best[x[0]], str(x[0])))


# ---------------------------------------------------------------- score normalization
def minmax(scores: Mapping[Id, float]) -> dict[Id, float]:
    """Map scores to [0, 1]: (s - min) / (max - min). If all scores are equal (or there is
    one), every item gets 1.0: each is the best its retriever had to offer."""
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    if hi - lo <= 1e-12:
        return {d: 1.0 for d in scores}
    return {d: (s - lo) / (hi - lo) for d, s in scores.items()}


def zscore(scores: Mapping[Id, float]) -> dict[Id, float]:
    """(s - mean) / stdev (population). All equal -> 0.0 for everybody."""
    if not scores:
        return {}
    vals = list(scores.values())
    mu = statistics.fmean(vals)
    sd = statistics.pstdev(vals)
    if sd <= 1e-12:
        return {d: 0.0 for d in scores}
    return {d: (s - mu) / sd for d, s in scores.items()}


NORMALIZERS = {"minmax": minmax, "zscore": zscore, "none": lambda s: dict(s)}


def weighted_fusion(score_lists: Sequence[Mapping[Id, float]], weights: Optional[Sequence[float]] = None,
                    normalize: str = "minmax", missing: float = 0.0) -> list[tuple[Id, float]]:
    """Normalize each list, then fused(d) = sum_i w_i * norm_i(d). An id absent from list i
    gets `missing` for it (0.0 = "as bad as the worst item this list returned").
    Returns [(id, score)] best first; ties as in rrf()."""
    weights = list(weights) if weights is not None else [1.0] * len(score_lists)
    if len(weights) != len(score_lists):
        raise ValueError("one weight per list")
    norm = NORMALIZERS[normalize]
    normed = [norm(s) for s in score_lists]
    ids: list[Id] = []
    best: dict[Id, int] = {}
    for s in score_lists:
        for r, d in enumerate(sorted(s, key=lambda x: -s[x]), start=1):
            if d not in best:
                ids.append(d)
            best[d] = min(best.get(d, r), r)
    fused = {d: math.fsum(w * n.get(d, missing) for w, n in zip(weights, normed)) for d in ids}
    return sorted(fused.items(), key=lambda x: (-x[1], best[x[0]], str(x[0])))


__all__ = ["rrf", "minmax", "zscore", "NORMALIZERS", "weighted_fusion"]
