"""Vectors: math helpers and vector stores (lesson 10; lesson 11 adds managed databases here).

    from ragkit.vectors import NumpyVectorStore, FaissVectorStore, VectorStore, cosine_top_k
"""

from .base import METRICS, VectorStore
from .faiss_store import FaissVectorStore
from .numpy_store import NumpyVectorStore
from .vecmath import (as_matrix, bytes_per_vector, cosine_top_k, l2_normalize, similarity, top_k,
                      truncate_dims)

STORES = {"numpy": NumpyVectorStore, "faiss": FaissVectorStore}


def make_store(spec: str = "numpy", metric: str = "cosine", dim=None) -> VectorStore:
    """"numpy" | "faiss" | "faiss:HNSW32" | "faiss:IVF64,Flat" ... (lesson 11 registers more in STORES)."""
    kind, _, arg = spec.partition(":")
    if kind == "faiss":
        return FaissVectorStore(dim=dim, metric=metric, index=arg or "Flat")
    if kind not in STORES:
        raise ValueError(f"unknown store {spec!r}; known: {sorted(STORES)}")
    return STORES[kind](dim=dim, metric=metric)


__all__ = ["VectorStore", "METRICS", "NumpyVectorStore", "FaissVectorStore", "STORES", "make_store",
           "as_matrix", "l2_normalize", "similarity", "top_k", "cosine_top_k", "truncate_dims",
           "bytes_per_vector"]
