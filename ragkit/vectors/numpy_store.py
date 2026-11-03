"""NumpyVectorStore: exact (brute-force) search with one matrix-vector product.

For the Acme corpus (a few hundred chunks) this is the right answer, not a toy: 300 x 384
floats is 460 KB and a query takes microseconds. Exact search stays practical up to roughly
a million vectors on one machine (a 1M x 384 float32 matrix is 1.5 GB, one query ~0.1 s
with BLAS); past that, or under tight latency, you want an ANN index (FaissVectorStore,
lesson 11's databases).

Filtering is exact pre-filtering: rows that fail `where` are removed before scoring.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence, Union

import numpy as np

from ..retrieval.base import Where, matches
from ..types import Chunk, Hit
from .base import METRICS, check_batch, make_hits
from .vecmath import l2_normalize, similarity, top_k


class NumpyVectorStore:
    name = "numpy"

    def __init__(self, dim: Optional[int] = None, metric: str = "cosine"):
        if metric not in METRICS:
            raise ValueError(f"metric must be one of {METRICS}")
        self.dim = dim
        self.metric = metric
        self._rows: dict[str, tuple[Chunk, np.ndarray]] = {}
        self._cache: Optional[tuple[list[Chunk], np.ndarray]] = None

    def __len__(self) -> int:
        return len(self._rows)

    def add(self, chunks: Sequence[Chunk], vectors) -> None:
        chunks = list(chunks)
        if not chunks:
            return
        v = check_batch(chunks, vectors, self.dim)
        self.dim = v.shape[1]
        if self.metric == "cosine":
            v = l2_normalize(v)
        for c, row in zip(chunks, v):
            self._rows[c.id] = (c, row)
        self._cache = None

    def remove(self, doc_id: str) -> int:
        ids = [cid for cid, (c, _) in self._rows.items() if c.doc_id == doc_id]
        for cid in ids:
            del self._rows[cid]
        if ids:
            self._cache = None
        return len(ids)

    def _matrix(self) -> tuple[list[Chunk], np.ndarray]:
        if self._cache is None:
            chunks = [c for c, _ in self._rows.values()]
            m = (np.stack([v for _, v in self._rows.values()]) if self._rows
                 else np.zeros((0, self.dim or 0), dtype=np.float32))
            self._cache = (chunks, m)
        return self._cache

    def vectors(self) -> tuple[list[Chunk], np.ndarray]:
        """All chunks and their (stored) vectors, row-aligned. For explorers and benchmarks."""
        return self._matrix()

    def search(self, vector, k: int = 5, where: Where = None) -> list[Hit]:
        chunks, m = self._matrix()
        if where is not None:
            keep = [i for i, c in enumerate(chunks) if matches(c, where)]
            chunks, m = [chunks[i] for i in keep], m[keep]
        if not chunks:
            return []
        idx, scores = top_k(similarity(vector, m, self.metric), k)
        return make_hits([chunks[i] for i in idx], scores, self.name)

    # -- persistence: vectors.npy + chunks.jsonl (row-aligned)
    def save(self, directory: Union[str, Path]) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        chunks, m = self._matrix()
        np.save(d / "vectors.npy", m)
        with open(d / "chunks.jsonl", "w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        (d / "store.json").write_text(json.dumps({"dim": self.dim, "metric": self.metric}))

    @classmethod
    def load(cls, directory: Union[str, Path]) -> "NumpyVectorStore":
        d = Path(directory)
        info = json.loads((d / "store.json").read_text())
        store = cls(dim=info["dim"], metric=info["metric"])
        with open(d / "chunks.jsonl", encoding="utf-8") as f:
            chunks = [Chunk.from_dict(json.loads(line)) for line in f if line.strip()]
        store.add(chunks, np.load(d / "vectors.npy"))
        return store
