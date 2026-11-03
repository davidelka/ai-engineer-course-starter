"""Your code for lesson 10. Each part is checked by tests in ./tests.

Reference versions exist in ragkit (ragkit/vectors/vecmath.py, ragkit/metrics.py,
ragkit/embed/cache.py). Try not to peek before your tests pass.

    python -m pytest -q labs/10-embeddings/tests

Only numpy and the standard library are needed.
"""

from __future__ import annotations

import hashlib  # noqa: F401  (exercise 4)
from collections.abc import MutableMapping
from typing import Callable, Iterable, Optional, Sequence

import numpy as np


# ------------------------------------------------------------------ exercise 2
def l2_normalize(x) -> np.ndarray:
    """Scale every row of x to length 1 (Euclidean norm).

    - x is array-like of shape (n, d) or (d,). A 1-D input is treated as ONE row and the
      result has shape (1, d). Always return a NEW float32 array; do not modify x.
    - A row whose norm is 0 (or below 1e-12) stays all zeros: no division by zero, no NaN.

        l2_normalize([3, 4])             -> [[0.6, 0.8]]
        l2_normalize([[3, 4], [0, 0]])   -> [[0.6, 0.8], [0.0, 0.0]]
    """
    raise NotImplementedError("exercise 2: l2_normalize")


def cosine_top_k(query, matrix, k: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Exact nearest neighbors of `query` among the rows of `matrix`, by cosine similarity.

    - query: shape (d,); matrix: shape (n, d). Neither is assumed to be normalized.
    - Return (indices, scores): two 1-D numpy arrays of length min(k, n), best first.
      indices are row numbers (ints), scores the cosine similarities (floats in [-1, 1]).
    - Ties: the lower row index comes first.
    - k larger than n returns all n rows; an empty matrix (n == 0) returns two empty arrays.
    - Use vectorized numpy (normalize, one matrix-vector product), not a Python loop over rows.
      Bonus: np.argpartition selects the top k in O(n) before sorting only those k.

        m = [[10, 0], [0.6, 0.8], [0, 1]]
        cosine_top_k([1, 0], m, 2)  -> (array([0, 1]), array([1.0, 0.6]))
        # row 0 points exactly where the query points: cosine 1.0. Its length (10) plays no
        # role. With a raw dot product, row 0 would score 10 and a long vector in a slightly
        # wrong direction could beat a short one in the right direction.
    """
    raise NotImplementedError("exercise 2: cosine_top_k")


# ------------------------------------------------------------------ exercise 3
# All three work at DOCUMENT level. `ranked` is the list of document ids in the order the
# retriever returned their chunks, and MAY contain duplicates (two chunks of one document).
# First deduplicate: keep each document's first position, drop its later occurrences.
#     ranked = ["x", "a", "x", "b"]   ->  document ranking ["x", "a", "b"]

def recall_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of the relevant documents that appear among the first k documents of the
    deduplicated ranking. Raise ValueError if `relevant` is empty (recall is undefined).

        recall_at_k(["x", "a", "x", "b", "c"], ["a", "b"], 2)  -> 0.5   (ranking x, a, b, c)
        recall_at_k(["x", "a", "x", "b", "c"], ["a", "b"], 3)  -> 1.0
    """
    raise NotImplementedError("exercise 3: recall_at_k")


def reciprocal_rank(ranked: Sequence[str], relevant: Iterable[str], k: Optional[int] = None) -> float:
    """1 / (1-based position of the first relevant document in the deduplicated ranking),
    looking only at the first k documents when k is given. 0.0 if none is found.
    MRR is the mean of this over all questions.

        reciprocal_rank(["x", "a", "x", "b"], ["b"])        -> 1/3
        reciprocal_rank(["x", "a", "x", "b"], ["b"], k=2)   -> 0.0
    """
    raise NotImplementedError("exercise 3: reciprocal_rank")


# ------------------------------------------------------------------ exercise 4
def cache_key(model_id: str, kind: str, text: str) -> str:
    """The cache key of one embedding: the sha256 hex digest (64 chars) of the UTF-8 bytes of
    model_id + "\\x1f" + kind + "\\x1f" + text   ("\\x1f" is the ASCII unit separator).
    kind is "query" or "document". The SAME function is used by ragkit's CachedEmbedder, so
    your keys must match it exactly (a test checks this)."""
    raise NotImplementedError("exercise 4: cache_key")


def embed_with_cache(texts: Sequence[str], embed_fn: Callable[[list[str]], np.ndarray],
                     cache: MutableMapping, model_id: str, kind: str = "document") -> np.ndarray:
    """Return the vectors of `texts` (shape (len(texts), d), float32, in the order of `texts`),
    paying the model only for what is not cached.

    - Look up every text in `cache` (a dict-like: key -> 1-D vector) by cache_key(model_id,
      kind, text). Use cache.get(key) (it returns None for a miss).
    - Call embed_fn AT MOST ONCE, with the missing texts only, each distinct text once, in
      the order they first appear. Do not call it at all if nothing is missing.
      embed_fn(list_of_str) returns an array of shape (len(list), d).
    - Store every new vector in the cache under its key, then build the result.
    - Duplicated input texts get the same vector (and are embedded once).
    - If embed_fn returns a different number of vectors than it was given, raise RuntimeError.
    """
    raise NotImplementedError("exercise 4: embed_with_cache")
