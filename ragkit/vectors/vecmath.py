"""Vector math used by every dense component (lesson 10). numpy only.

Three similarity measures, and why normalization makes them agree:
    dot(a, b)     = sum(a_i * b_i)
    cosine(a, b)  = dot(a, b) / (|a| * |b|)          angle only, length ignored
    L2(a, b)      = |a - b|,  and  |a - b|^2 = |a|^2 + |b|^2 - 2 dot(a, b)
If every vector has length 1, then cosine == dot, and |a - b|^2 = 2 - 2 cos(a, b): all three
produce the SAME ranking. That is why we L2-normalize once, at write time, and then use the
cheapest operation (a matrix-vector product) at query time.

Matryoshka truncation: models trained with Matryoshka Representation Learning put the most
important information in the first dimensions, so `truncate_dims(v, 256)` keeps a useful
vector. It must be re-normalized after cutting. Models NOT trained that way (multilingual-e5)
also "work" after truncation, just worse: the lab measures how much.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

EPS = 1e-12


def as_matrix(x) -> np.ndarray:
    """float32, 2-D (a single vector becomes one row)."""
    a = np.asarray(x, dtype=np.float32)
    return a.reshape(1, -1) if a.ndim == 1 else a


def l2_normalize(x) -> np.ndarray:
    """Rows scaled to length 1. All-zero rows stay zero (no NaN). Returns float32."""
    a = as_matrix(x).copy()
    n = np.linalg.norm(a, axis=1, keepdims=True)
    np.divide(a, n, out=a, where=n > EPS)
    a[(n <= EPS).ravel()] = 0.0
    return a


def similarity(query, matrix, metric: str = "cosine") -> np.ndarray:
    """Scores of one query against every row, HIGHER IS BETTER for every metric
    (for "l2" the score is the negative squared distance)."""
    q = as_matrix(query)[0]
    m = as_matrix(matrix)
    if metric == "cosine":
        return l2_normalize(m) @ l2_normalize(q)[0]
    if metric == "dot":
        return m @ q
    if metric == "l2":
        d = m - q
        return -np.einsum("ij,ij->i", d, d)
    raise ValueError(f"unknown metric {metric!r} (cosine | dot | l2)")


def top_k(scores, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Indices and scores of the k largest scores, best first; ties broken by lower index.
    O(n) argpartition, then a sort of only the k winners."""
    s = np.asarray(scores, dtype=np.float32).ravel()
    n = s.shape[0]
    k = max(0, min(int(k), n))
    if k == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)
    if k < n:
        # include every element tied with the k-th best so the tie-break below is exact
        kth = np.partition(s, n - k)[n - k]
        cand = np.nonzero(s >= kth)[0]
    else:
        cand = np.arange(n)
    order = np.lexsort((cand, -s[cand]))[:k]
    idx = cand[order].astype(np.int64)
    return idx, s[idx]


def cosine_top_k(query, matrix, k: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Exact nearest neighbors by cosine similarity: (indices, scores), best first."""
    if as_matrix(matrix).shape[0] == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)
    return top_k(similarity(query, matrix, "cosine"), k)


def truncate_dims(x, dims: Optional[int], *, renormalize: bool = True) -> np.ndarray:
    """Keep the first `dims` dimensions (Matryoshka style), then re-normalize."""
    a = as_matrix(x)
    if dims is None or dims >= a.shape[1]:
        return l2_normalize(a) if renormalize else a.copy()
    if dims <= 0:
        raise ValueError("dims must be positive")
    out = np.ascontiguousarray(a[:, :dims])
    return l2_normalize(out) if renormalize else out


def bytes_per_vector(dim: int, dtype: str = "float32") -> int:
    return dim * {"float32": 4, "float16": 2, "int8": 1, "binary": 1 / 8}[dtype]
