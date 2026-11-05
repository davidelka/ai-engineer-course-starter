"""Your code for lesson 11. Each part is checked by tests in ./tests.

Reference versions exist in ragkit (ragkit/vectors/bench.py, ragkit/vectors/sizing.py,
ragkit/vectors/filters.py). Try not to peek before your tests pass.

    python -m pytest -q labs/11-managed-vectors/tests

Only numpy and the standard library are needed.
"""

from __future__ import annotations

from typing import Hashable, Optional, Sequence

import numpy as np


# ------------------------------------------------------------------ exercise 2
def recall_at_k(found: Sequence[Hashable], truth: Sequence[Hashable], k: int) -> float:
    """recall@k of an approximate result against the exact one.

    found: ids returned by the ANN index, best first. truth: ids returned by EXACT search, best
    first. Returns the fraction of truth's first k ids that appear in found's first k ids
    (a float in [0, 1]). If truth is empty, return 1.0 (there was nothing to find).

        recall_at_k([1, 2, 9], [1, 2, 3], 3)  -> 0.666...
        recall_at_k([3, 2, 1], [1, 2, 3], 3)  -> 1.0     (order inside the top k does not matter)
        recall_at_k([1, 2], [1, 2, 3, 4], 4)  -> 0.5     (missing results count as misses)
    Stuck? HINTS.md -> recall_at_k
    """
    raise NotImplementedError("exercise 2: recall_at_k")


def pareto_frontier(points: Sequence[tuple[float, float]]) -> list[int]:
    """Indices of the Pareto-optimal points, sorted by latency ascending.

    Each point is (latency_ms, recall): LOWER latency is better, HIGHER recall is better.
    Point a dominates point b if a.latency <= b.latency and a.recall >= b.recall and they
    differ in at least one of the two. Return the indices of points no other point dominates.
    Exact duplicates (same latency AND recall): keep only the first occurrence (lowest index).

        pts = [(1.0, 0.80), (2.0, 0.95), (1.5, 0.70), (3.0, 0.95), (4.0, 0.99)]
        pareto_frontier(pts) -> [0, 1, 4]
        # (1.5, 0.70) is dominated by (1.0, 0.80): slower AND worse.
        # (3.0, 0.95) is dominated by (2.0, 0.95): same recall, slower.

    Why it matters: in a sweep of ef_search (or M, or quantization) most configurations are
    simply worse than another one. Only the frontier is worth considering; picking a point on
    it is then a business decision (how much latency is 1% more recall worth?).
    Stuck? HINTS.md -> pareto_frontier
    """
    raise NotImplementedError("exercise 2: pareto_frontier")


# ------------------------------------------------------------------ exercise 3
def exact_filtered_top_k(query, matrix, mask, k: int) -> np.ndarray:
    """The ground truth for filtered search: the k rows most similar to `query` by COSINE
    similarity, among the rows where mask is True.

    - query: shape (d,); matrix: shape (n, d), not assumed normalized; mask: n booleans.
    - Returns a 1-D int array of ROW INDICES INTO THE FULL MATRIX (not into the filtered
      subset!), best first, length min(k, number of True rows).
    - Ties: the lower row index first. No row passes the filter -> an empty int array.
    - Vectorized numpy, no Python loop over rows.

        m = [[1, 0], [0, 1], [0.9, 0.1], [-1, 0]]
        exact_filtered_top_k([1, 0], m, [False, True, True, True], 2) -> array([2, 1])
        # row 0 is the best match overall but fails the filter.
    Stuck? HINTS.md -> exact_filtered_top_k
    """
    raise NotImplementedError("exercise 3: exact_filtered_top_k")


def filtered_recall(found: Sequence[int], exact: Sequence[int], k: int) -> float:
    """recall@k of a FILTERED ANN result against exact_filtered_top_k.

    - If only 3 rows pass the filter, returning exactly those 3 is perfect recall (1.0), even
      with k = 10. If exact is empty (nothing passes the filter), return 1.0.
    - Only the first k of `found` count. A result list SHORTER than the true one (the classic
      post-filtering failure: the filter threw away most candidates) loses recall.

        filtered_recall([5, 7], [5, 7, 9], 10)      -> 0.666...
        filtered_recall([5, 7, 9], [9, 5, 7], 10)   -> 1.0
        filtered_recall([], [], 10)                 -> 1.0
    Stuck? HINTS.md -> filtered_recall
    """
    raise NotImplementedError("exercise 3: filtered_recall")


# ------------------------------------------------------------------ exercise 5
def index_ram_bytes(n: int, dim: int, m: int = 16, quantization: Optional[str] = None,
                    originals_in_ram: Optional[bool] = None) -> float:
    """Estimated RAM (bytes, a float) of an HNSW index of n vectors of `dim` dimensions.

    The cost model the tests use (turn it into a formula yourself):
      - graph, per node: layer 0 holds up to 2m neighbor ids of 4 bytes plus a 4-byte count;
        a node has on average 1/(m-1) upper layers, each with up to m ids plus a count.
        m < 2: the graph costs 0 bytes.
      - quantized copy (only when quantization is not None and not "float32"), bytes per
        dimension: "float16" 2, "int8" or "scalar" 1, "binary" 1 bit (rounded up to whole bytes).
      - float32 originals: 4 bytes per dimension, counted only if originals_in_ram. Default
        (None): True without quantization, False with it (the originals then live on disk and
        are read only to rescore the top candidates).
    Any other quantization string -> ValueError.

        index_ram_bytes(1_000_000, 384)                       -> ~1.672e9  (1.536e9 + 136.5e6)
        index_ram_bytes(1_000_000, 384, quantization="binary")-> ~1.845e8  (48e6 + 136.5e6)
    Stuck? HINTS.md -> index_ram_bytes
    """
    raise NotImplementedError("exercise 5: index_ram_bytes")


# ------------------------------------------------------------------ exercise 6
def acl_where(role: str) -> dict:
    """The metadata filter (a ragkit `where` dict) that lets `role` retrieve exactly the chunks
    the Acme access matrix allows. The filter runs in the database BEFORE ranking, so a
    forbidden chunk can never be returned, nor push others out.

    The matrix (the same as lesson 24's guardkit/acl.py):
      - "public" chunks: every role, including "contractor".
      - "internal" chunks: every role except "contractor".
      - "confidential" chunks: role "security", OR a role whose department equals the chunk's
        `department` metadata. Role -> department: "engineering" -> "engineering",
        "support" -> "sales_support", "hr" -> "hr", "finance" -> "finance".
        "security", "employee", "contractor" have no department.
      - any other classification (missing, "restricted", misspelled): nobody.
      - an unknown role: nothing at all (fail closed).

    The `where` language (ragkit.vectors.filters):
        {"classification": ["public", "internal"]}        value is one of the list
        {"classification": "confidential", "department": "hr"}   both must hold (AND)
        {"$or": [where_a, where_b]}                        at least one branch holds
        {"classification": []}                             matches nothing

    The data (data/acme/corpus/docs/, 55 documents): 47 internal, 4 public, 4 confidential:
        eng-pm-2026-03-scheduler  engineering  Postmortem: Duplicate scheduled runs
        eng-pm-2026-06-billing    engineering  Postmortem: EUR invoices overcharged
        eng-pm-2026-08-api        engineering  Postmortem: flow-api outage (Aug 19, 2026)
        hr-relocation             hr           Relocation Policy
    Stuck? HINTS.md -> acl_where
    """
    raise NotImplementedError("exercise 6: acl_where")
