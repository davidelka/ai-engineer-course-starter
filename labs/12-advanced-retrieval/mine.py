"""Your code for lesson 12. Each part is checked by tests in ./tests.

Reference versions exist in ragkit (ragkit/fusion.py, ragkit/versions.py). Try not to peek
before your tests pass.

    python -m pytest -q labs/12-advanced-retrieval/tests

Only the standard library is needed (and ragkit's Hit/Chunk types for exercise 5).
"""

from __future__ import annotations

import math  # noqa: F401  (math.fsum: an exactly rounded sum, so the order of terms does not matter)
from dataclasses import replace  # noqa: F401  (exercise 5: copy a Hit with a new rank)
from typing import Hashable, Mapping, Optional, Sequence


# ------------------------------------------------------------------ exercise 1
def rrf(rankings: Sequence[Sequence[Hashable]], k: float = 60.0,
        weights: Optional[Sequence[float]] = None) -> list[tuple[Hashable, float]]:
    """Reciprocal Rank Fusion. `rankings` is a list of ranked id lists, best first (e.g. the
    chunk ids from BM25 and the chunk ids from the dense retriever). Return [(id, score)] for
    EVERY id that appears in any list, best first.

        score(d) = sum over the lists that contain d of   w_i / (k + rank_i(d))

    - rank is 1-based: the first item of a list has rank 1.
    - An id missing from a list contributes nothing for that list (not a penalty, not 0-rank).
    - If an id appears twice in the SAME list, only its first (best) position counts.
    - weights: one per list, default 1.0 each. Raise ValueError if the count does not match,
      or if k < 0.
    - Sum the terms of each id with math.fsum (exact, so the list order cannot change a tie).
    - Order: higher score first. Ties: the id with the better (lower) best rank in any single
      list first; if still tied, by str(id) ascending.

        rrf([["a", "b", "c"], ["c", "a"]], k=60)
        -> [("a", 1/61 + 1/62), ("c", 1/63 + 1/61), ("b", 1/62)]
           a = 0.032522, c = 0.032266, b = 0.016129
        rrf([["x", "y"], ["y", "x"]])  -> x and y tie exactly (1/61 + 1/62 each), both have
           best rank 1, so str order decides: [("x", ...), ("y", ...)]
    """
    raise NotImplementedError("exercise 1: rrf")


# ------------------------------------------------------------------ exercise 2
def minmax_normalize(scores: Mapping[Hashable, float]) -> dict[Hashable, float]:
    """Map one retriever's scores to [0, 1]: (s - min) / (max - min).

    - Empty input -> {}.
    - If all scores are equal (or there is only one), every id gets 1.0: each is the best
      that retriever returned. (Treat max - min <= 1e-12 as equal.)

        minmax_normalize({"a": 12.0, "b": 7.0, "c": 2.0}) -> {"a": 1.0, "b": 0.5, "c": 0.0}
    """
    raise NotImplementedError("exercise 2: minmax_normalize")


def weighted_fusion(score_lists: Sequence[Mapping[Hashable, float]],
                    weights: Optional[Sequence[float]] = None,
                    missing: float = 0.0) -> list[tuple[Hashable, float]]:
    """Weighted score fusion with min-max normalization. score_lists[i] is {id: raw score}
    from retriever i (BM25 scores like 14.2, cosine like 0.83: different scales).

        fused(d) = sum_i  weights[i] * minmax_normalize(score_lists[i]).get(d, missing)

    - weights default to 1.0 each; ValueError if the count does not match the lists.
    - Return [(id, fused)] for every id in any list, best first. Sum with math.fsum.
    - Ties: the better best rank first, where an id's rank in list i is its position when
      that list is sorted by raw score descending (1-based); then str(id) ascending.

        weighted_fusion([{"a": 10, "b": 5, "c": 0}, {"b": 0.9, "c": 0.8}], [0.5, 0.5])
        a: 0.5*1.0 + 0.5*0 = 0.5     b: 0.5*0.5 + 0.5*1.0 = 0.75     c: 0.5*0 + 0.5*0 = 0.0
        -> [("b", 0.75), ("a", 0.5), ("c", 0.0)]
        Note c: it was 2nd for the dense retriever, but min-max made it 0.0, exactly like
        an id that retriever never returned. That is the pitfall exercise 2 demonstrates.
    """
    raise NotImplementedError("exercise 2: weighted_fusion")


# ------------------------------------------------------------------ exercise 5
def drop_superseded(hits: Sequence) -> list:
    """Version-aware post-filter. `hits` is a ranked list of ragkit Hit objects (best first).
    Each hit.chunk.doc_id is a document id; hit.chunk.meta.get("supersedes") is None, a
    document id (str) or a list of ids that THIS document replaces. (Only the newer document
    says what it replaces; the old one carries no marker.)

    Drop every hit whose document is listed in the `supersedes` of ANOTHER document that is
    also present in `hits`. With A, B and C all present, where C supersedes B and B supersedes
    A, only C survives (B is replaced by C, A by B).

    - Keep the order of the remaining hits; return NEW Hit objects with rank renumbered
      1..n (dataclasses.replace(h, rank=i)); do not modify the input hits.
    - Never drop a document because of itself (a doc that lists itself in supersedes).
      A cycle (A supersedes B, B supersedes A, both present) drops both; that is bad data,
      and the test only checks that your function returns.
    - If the newer version was NOT retrieved, the old one stays: an old answer with its date
      is better than none.

        hits (doc ids, in order): hr-vacation-2024, hr-vacation-2026, hr-sick-leave
        hr-vacation-2026 has supersedes="hr-vacation-2024"
        -> hr-vacation-2026 (rank 1), hr-sick-leave (rank 2)
    """
    raise NotImplementedError("exercise 5: drop_superseded")
