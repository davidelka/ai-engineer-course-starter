"""FaissVectorStore: the same contract as NumpyVectorStore, backed by a FAISS index.

    FaissVectorStore(index="Flat")            exact, same results as NumpyVectorStore
    FaissVectorStore(index="HNSW32")          graph ANN: M=32 neighbors per node
    FaissVectorStore(index="IVF64,Flat")      64 k-means cells, search `nprobe` of them
    FaissVectorStore(index="IVF64,PQ16")      cells + product quantization (16 bytes/vector)

`index` is a faiss.index_factory string. Requires `pip install faiss-cpu` (imported lazily).

Design choices, all of which a managed database makes for you (lesson 11):
- The store keeps a float32 copy of every vector and (re)builds the FAISS index lazily on the
  first search after a change. That makes remove() and upserts trivial (HNSW cannot delete,
  IVF needs training) at the price of 2x memory and a rebuild after each ingest batch.
- Metadata filters: FAISS knows ids, not metadata. We compute the allowed rows with
  ragkit's `matches`, then
    * if few rows pass (<= brute_force_below), score them exactly with numpy (what query
      planners in vector databases also do for selective filters);
    * otherwise pass an IDSelectorBatch in the search parameters, so FAISS skips the rest.
  Filtered HNSW search can lose recall when the filter is selective, because the graph walk
  has to pass through excluded nodes: that is a real limitation, not a bug of this wrapper.
- Cosine: vectors are L2-normalized and the index uses inner product.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from ..retrieval.base import Where, matches
from ..types import Chunk, Hit
from .base import METRICS, check_batch, make_hits
from .vecmath import l2_normalize, similarity, top_k


def _faiss():
    try:
        import faiss  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError("FaissVectorStore needs faiss-cpu: uv pip install faiss-cpu") from exc
    return faiss


class FaissVectorStore:
    def __init__(self, dim: Optional[int] = None, metric: str = "cosine", index: str = "Flat", *,
                 nprobe: int = 8, ef_search: int = 64, brute_force_below: int = 2000):
        if metric not in METRICS:
            raise ValueError(f"metric must be one of {METRICS}")
        self.dim, self.metric, self.spec = dim, metric, index
        self.nprobe, self.ef_search, self.brute_force_below = nprobe, ef_search, brute_force_below
        self.name = f"faiss:{index}"
        self._rows: dict[str, tuple[Chunk, np.ndarray]] = {}
        self._built = None          # (faiss index, chunks list, matrix) or None when dirty

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
        self._built = None

    def remove(self, doc_id: str) -> int:
        ids = [cid for cid, (c, _) in self._rows.items() if c.doc_id == doc_id]
        for cid in ids:
            del self._rows[cid]
        if ids:
            self._built = None
        return len(ids)

    def build(self):
        """Train (IVF/PQ) and fill the FAISS index from the stored vectors."""
        faiss = _faiss()
        chunks = [c for c, _ in self._rows.values()]
        m = np.ascontiguousarray(np.stack([v for _, v in self._rows.values()]).astype(np.float32))
        fmetric = faiss.METRIC_L2 if self.metric == "l2" else faiss.METRIC_INNER_PRODUCT
        index = faiss.index_factory(m.shape[1], self.spec, fmetric)
        if not index.is_trained:
            index.train(m)          # k-means for IVF cells / PQ codebooks; needs enough rows
        index.add(m)
        self._built = (index, chunks, m)
        return index

    @property
    def index(self):
        if self._built is None:
            self.build()
        return self._built[0]

    def _params(self, sel):
        faiss = _faiss()
        if "HNSW" in self.spec and "IVF" not in self.spec:
            return faiss.SearchParametersHNSW(sel=sel, efSearch=max(self.ef_search, 1))
        if "IVF" in self.spec:
            return faiss.SearchParametersIVF(sel=sel, nprobe=self.nprobe)
        return faiss.SearchParameters(sel=sel)

    def search(self, vector, k: int = 5, where: Where = None) -> list[Hit]:
        if not self._rows:
            return []
        index = self.index
        _, chunks, m = self._built
        q = np.asarray(vector, dtype=np.float32).reshape(1, -1)
        if self.metric == "cosine":
            q = l2_normalize(q)
        sel = None
        if where is not None:
            keep = np.array([i for i, c in enumerate(chunks) if matches(c, where)], dtype=np.int64)
            if keep.size == 0:
                return []
            if keep.size <= self.brute_force_below:
                idx, sc = top_k(similarity(q, m[keep], self.metric), k)
                return make_hits([chunks[keep[i]] for i in idx], sc, self.name + "+exact")
            sel = _faiss().IDSelectorBatch(keep)
        k_eff = min(k, len(chunks))
        dist, ids = index.search(q, k_eff, params=self._params(sel))
        out_c, out_s = [], []
        for d, i in zip(dist[0], ids[0]):
            if i < 0:
                continue                      # fewer than k results reachable
            out_c.append(chunks[i])
            out_s.append(-float(d) if self.metric == "l2" else float(d))   # FAISS L2 = squared distance
        return make_hits(out_c, out_s, self.name)
