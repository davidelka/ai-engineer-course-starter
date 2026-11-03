"""Measuring vector indexes (lesson 11): recall against exact search, latency, Pareto frontier,
and filtered-search correctness. Reference implementations of the lab's mine.py exercises.

    rows = sweep(lambda q, k, ef: ids_from(index.search(q, k, ef=ef)), queries, truth, [16, 32, 64])
    for i in pareto_frontier([(r["ms"], r["recall"]) for r in rows]): print(rows[i])

Conventions
- "ids" are anything hashable (row numbers, chunk ids). A result list is best-first.
- recall@k of an approximate result = |found[:k] ∩ truth[:k]| / |truth[:k]|, where truth is
  the EXACT top-k (brute force). It measures the index, not relevance: an index can have
  recall 1.0 and still return useless chunks if the embeddings are bad (lesson 10's metrics
  measure that).
"""

from __future__ import annotations

import time
from typing import Callable, Hashable, Iterable, Optional, Sequence

import numpy as np

from .vecmath import similarity


def recall_ids(found: Sequence[Hashable], truth: Sequence[Hashable], k: int) -> float:
    t = list(truth)[:k]
    if not t:
        return 1.0
    return len(set(list(found)[:k]) & set(t)) / len(t)


def mean_recall(found: Iterable[Sequence], truth: Iterable[Sequence], k: int) -> float:
    vals = [recall_ids(f, t, k) for f, t in zip(found, truth)]
    return float(np.mean(vals)) if vals else 1.0


def pareto_frontier(points: Sequence[tuple[float, float]]) -> list[int]:
    """Indices of the points not dominated by any other, sorted by latency (ascending).

    A point is (latency, recall): lower latency is better, higher recall is better.
    Point a DOMINATES b if a.latency <= b.latency and a.recall >= b.recall and a != b in at
    least one coordinate. Exact duplicates: only the first occurrence (lowest index) is kept.
    """
    order = sorted(range(len(points)), key=lambda i: (points[i][0], -points[i][1], i))
    out: list[int] = []
    best = -np.inf
    seen: set = set()
    for i in order:
        lat, rec = points[i]
        if (lat, rec) in seen:
            continue
        seen.add((lat, rec))
        if rec > best:
            out.append(i)
            best = rec
    return out


def sweep(search: Callable[[np.ndarray, int, object], Sequence[Hashable]], queries: np.ndarray,
          truth: Sequence[Sequence[Hashable]], params: Iterable, k: int = 10,
          warmup: int = 5) -> list[dict]:
    """Run `search(query, k, param)` for every query and every param; return one row per param:
    {"param", "recall", "ms" (mean per query), "p95_ms"}. Queries run one at a time (latency
    as a user sees it), after `warmup` untimed queries."""
    rows = []
    for p in params:
        for q in queries[:warmup]:
            search(q, k, p)
        found, times = [], []
        for q in queries:
            t0 = time.perf_counter()
            found.append(list(search(q, k, p)))
            times.append((time.perf_counter() - t0) * 1000)
        rows.append({"param": p, "recall": mean_recall(found, truth, k),
                     "ms": float(np.mean(times)), "p95_ms": float(np.percentile(times, 95))})
    return rows


# ---------------------------------------------------------------- filtered search
def exact_filtered_top_k(query, matrix, mask, k: int, metric: str = "cosine") -> np.ndarray:
    """Row indices (into `matrix`) of the k most similar rows among those where mask is True,
    best first; ties -> lower row index first. Fewer than k rows pass -> all of them."""
    mask = np.asarray(mask, dtype=bool)
    allowed = np.flatnonzero(mask)
    if allowed.size == 0 or k <= 0:
        return np.empty(0, dtype=np.int64)
    s = similarity(query, np.asarray(matrix)[allowed], metric)
    order = np.lexsort((allowed, -s))            # by score desc, then row index asc
    return allowed[order[:k]]


def filtered_recall(found: Sequence[int], exact: Sequence[int], k: int) -> float:
    """recall@k of a filtered ANN result against the exact filtered top-k.

    The denominator is min(k, len(exact)): when only 3 rows pass the filter, finding those 3
    is perfect recall. An empty `exact` (nothing passes) gives 1.0. Returning FEWER results
    than exist is the classic post-filtering failure and counts as missed results."""
    e = list(exact)[:k]
    if not e:
        return 1.0
    return len(set(list(found)[:k]) & set(e)) / len(e)


def post_filter(candidates: Sequence[int], mask, k: int) -> list[int]:
    """What naive post-filtering does: take the ANN candidates, drop those failing the filter,
    keep the first k. With a restrictive filter this returns fewer than k (often zero)."""
    mask = np.asarray(mask, dtype=bool)
    return [int(i) for i in candidates if mask[int(i)]][:k]


def violations(found: Sequence[int], mask) -> int:
    """How many returned rows FAIL the filter (must be 0; >0 is a correctness/ACL bug)."""
    mask = np.asarray(mask, dtype=bool)
    return sum(1 for i in found if not mask[int(i)])


def synth_clustered(n: int, dim: int = 384, clusters: int = 500, noise: float = 1.4,
                    seed: int = 0) -> np.ndarray:
    """Clustered unit vectors that behave like embeddings (see lesson 10's faiss_bench)."""
    rng = np.random.default_rng(seed)
    centers = rng.standard_normal((clusters, dim)).astype(np.float32)
    centers /= np.linalg.norm(centers, axis=1, keepdims=True)
    pick = rng.integers(0, clusters, n)
    x = centers[pick] + noise / np.sqrt(dim) * rng.standard_normal((n, dim)).astype(np.float32)
    return (x / np.linalg.norm(x, axis=1, keepdims=True)).astype(np.float32)


def exact_top_k_matrix(queries: np.ndarray, matrix: np.ndarray, k: int,
                       block: int = 256) -> np.ndarray:
    """Exact top-k row indices for many normalized queries (inner product), in blocks."""
    out = np.empty((queries.shape[0], k), dtype=np.int64)
    for i in range(0, queries.shape[0], block):
        s = queries[i:i + block] @ matrix.T
        part = np.argpartition(-s, kth=min(k, s.shape[1] - 1), axis=1)[:, :k]
        ps = np.take_along_axis(s, part, axis=1)
        o = np.argsort(-ps, axis=1, kind="stable")
        out[i:i + block] = np.take_along_axis(part, o, axis=1)
    return out


__all__ = ["recall_ids", "mean_recall", "pareto_frontier", "sweep", "exact_filtered_top_k",
           "filtered_recall", "post_filter", "violations", "synth_clustered", "exact_top_k_matrix"]
