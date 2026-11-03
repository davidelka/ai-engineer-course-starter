"""The VectorStore contract (lesson 10), implemented here by NumpyVectorStore (exact) and
FaissVectorStore (exact or approximate), and in lesson 11 by managed vector databases.

A vector store keeps (chunk, vector) pairs and answers "which k chunks have vectors closest
to this vector, among the chunks that pass this metadata filter?". It knows nothing about
text or embedding models: DenseRetriever (ragkit.dense) turns text into vectors and calls it.

    store.add(chunks, vectors)            vectors: float32 array (len(chunks), dim)
    store.remove(doc_id) -> int           every chunk of that document; returns how many
    store.search(vector, k, where) -> list[Hit]     best first, Hit.scores["vector"] set
    len(store), store.dim, store.metric

`where` has the semantics of ragkit.retrieval.base.matches (equality, membership, $gte...,
or a callable). The filter is applied BEFORE ranking: a store must never return fewer than k
hits just because the k nearest happened to be filtered out, and must never let a filtered
chunk into the results. A managed database translates the dict form into its own filter
language (Qdrant payload filter, pgvector WHERE clause) instead of calling matches().

Re-adding a chunk id replaces its vector (upsert), which is what incremental ingestion needs.
"""

from __future__ import annotations

from typing import Iterable, Protocol, Sequence, runtime_checkable

import numpy as np

from ..retrieval.base import Where
from ..types import Chunk, Hit

METRICS = ("cosine", "dot", "l2")


@runtime_checkable
class VectorStore(Protocol):
    dim: int
    metric: str

    def add(self, chunks: Sequence[Chunk], vectors: np.ndarray) -> None: ...

    def remove(self, doc_id: str) -> int: ...

    def search(self, vector: np.ndarray, k: int = 5, where: Where = None) -> list[Hit]: ...

    def __len__(self) -> int: ...


def check_batch(chunks: Sequence[Chunk], vectors, dim: int | None) -> np.ndarray:
    v = np.asarray(vectors, dtype=np.float32)
    if v.ndim != 2 or v.shape[0] != len(chunks):
        raise ValueError(f"expected {len(chunks)} vectors, got array of shape {v.shape}")
    if dim is not None and v.shape[1] != dim:
        raise ValueError(f"vector dim {v.shape[1]} != store dim {dim} (mixed embedding models?)")
    if not np.all(np.isfinite(v)):
        raise ValueError("vectors contain NaN or inf")
    return v


def make_hits(chunks: Iterable[Chunk], scores: Iterable[float], name: str) -> list[Hit]:
    return [Hit(chunk=c, score=float(s), rank=i + 1, scores={"vector": float(s)}, retriever=name)
            for i, (c, s) in enumerate(zip(chunks, scores))]
