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
    """Reciprocal Rank Fusion. `rankings` is a list of ranked id lists, best first (e.g. chunk
    ids from BM25 and from the dense retriever). Returns [(id, score)] for EVERY id that
    appears in any list, best first. The definition (the tests check exact values):

        score(d) = sum over the lists that contain d of   w_i / (k + rank_i(d))

    - rank is 1-based. A list without d adds nothing. A repeated id in one list: only its
      first (best) position counts.
    - weights: one per list, default 1.0 each. ValueError if the count does not match, or k < 0.
    - The sum must be exact (math.fsum), so the order of the lists cannot change a tie.
    - Order: higher score first; ties by the better (lower) best rank in any single list, then
      by str(id) ascending.

        rrf([["a", "b", "c"], ["c", "a"]], k=60)
        -> [("a", 1/61 + 1/62), ("c", 1/63 + 1/61), ("b", 1/62)]
        rrf([["x", "y"], ["y", "x"]])  -> exact tie, both best rank 1 -> [("x", ...), ("y", ...)]
    Stuck? HINTS.md -> rrf
    """
    raise NotImplementedError("exercise 1: rrf")


# ------------------------------------------------------------------ exercise 2
def minmax_normalize(scores: Mapping[Hashable, float]) -> dict[Hashable, float]:
    """Map one retriever's scores to [0, 1]: the minimum becomes 0.0, the maximum 1.0, linear in
    between.

    - Empty input -> {}.
    - All scores equal (or only one, or max - min <= 1e-12): every id gets 1.0, since each is
      the best that retriever returned.

        minmax_normalize({"a": 12.0, "b": 7.0, "c": 2.0}) -> {"a": 1.0, "b": 0.5, "c": 0.0}
    Stuck? HINTS.md -> minmax_normalize
    """
    raise NotImplementedError("exercise 2: minmax_normalize")


def weighted_fusion(score_lists: Sequence[Mapping[Hashable, float]],
                    weights: Optional[Sequence[float]] = None,
                    missing: float = 0.0) -> list[tuple[Hashable, float]]:
    """Weighted score fusion with min-max normalization. score_lists[i] is {id: raw score} from
    retriever i (BM25 scores like 14.2, cosine like 0.83: different scales).

        fused(d) = sum_i  weights[i] * minmax_normalize(score_lists[i]).get(d, missing)

    - weights default to 1.0 each; ValueError if the count does not match the lists.
    - Returns [(id, fused)] for every id in any list, best first. The sum must be exact
      (math.fsum).
    - Ties: the better best rank first, where an id's rank in list i is its 1-based position
      in that list sorted by raw score descending; then str(id) ascending.

        weighted_fusion([{"a": 10, "b": 5, "c": 0}, {"b": 0.9, "c": 0.8}], [0.5, 0.5])
        -> [("b", 0.75), ("a", 0.5), ("c", 0.0)]
        Note c: 2nd for the dense retriever, yet 0.0 after min-max, exactly like an id that
        retriever never returned. That is the pitfall exercise 2 demonstrates.
    Stuck? HINTS.md -> weighted_fusion
    """
    raise NotImplementedError("exercise 2: weighted_fusion")


# ------------------------------------------------------------------ exercise 5
def drop_superseded(hits: Sequence) -> list:
    """Version-aware post-filter. `hits` is a ranked list of ragkit Hit objects (best first).
    hit.chunk.doc_id is a document id; hit.chunk.meta.get("supersedes") is None, a document id
    (str) or a list of ids that THIS document replaces (only the newer document says so).

    Returns a list of NEW Hit objects (the input is not modified):
    - a hit is dropped when its document is listed in the `supersedes` of ANOTHER document
      that is also present in `hits`. With A, B, C present, C supersedes B, B supersedes A:
      only C survives.
    - the remaining hits keep their order, with rank renumbered 1..n.
    - a document never drops itself. A cycle (A supersedes B, B supersedes A, both present)
      drops both: bad data; the test only checks that the function returns.
    - if the newer version was NOT retrieved, the old one stays: an old answer with its date
      is better than none.

        hits (doc ids, in order): hr-vacation-2024, hr-vacation-2026, hr-sick-leave
        hr-vacation-2026 has supersedes="hr-vacation-2024"
        -> hr-vacation-2026 (rank 1), hr-sick-leave (rank 2)
    Stuck? HINTS.md -> drop_superseded
    """
    raise NotImplementedError("exercise 5: drop_superseded")
