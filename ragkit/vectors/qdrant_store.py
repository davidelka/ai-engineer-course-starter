"""QdrantVectorStore: the VectorStore contract on Qdrant (lesson 11).

    store = QdrantVectorStore(url="http://localhost:6333", collection="acme")  # docker compose
    store = QdrantVectorStore()                         # in-process ":memory:" mode (tests)
    dense = DenseRetriever(embedder, store=store)       # nothing else changes

Requires `pip install qdrant-client` (imported lazily).

What this adapter decides, and why
- Point ids: Qdrant accepts unsigned ints or UUIDs, not "doc#3". We use uuid5(chunk.id), so
  re-adding a chunk overwrites the same point (upsert), which is what incremental ingestion
  needs. The chunk id is also kept in the payload.
- Payload: every metadata key (classification, department, language, effective_date...) and
  doc_id/id/index/section are stored as TOP-LEVEL payload fields, so filters can use them;
  the full chunk is stored under "_chunk" so a hit can be turned back into a ragkit Chunk.
- Payload indexes are created BEFORE the first upsert (Qdrant builds the extra "filterable
  HNSW" edges only for fields that are indexed when the graph is built). Adding an index
  later works, but the graph must be rebuilt to benefit.
- HNSW knobs: m, ef_construct (build time, collection config), ef_search (query time,
  SearchParams.hnsw_ef), full_scan_threshold (KB; below it a filtered query is answered by
  exact scoring of the matching points), on_disk.
- Quantization: None | "scalar" (int8, 4x smaller) | "binary" (1 bit, 32x) | "product"
  (PQ, x16 here) | "turbo" (Qdrant 1.20 TurboQuant, bits4 here); with `rescore` and
  `oversampling` at query time.
- `exact=True` asks Qdrant for brute-force search: the ground truth for recall measurements.
- `acorn=True` enables ACORN (Qdrant >= 1.16) for restrictive multi-field filters.

IMPORTANT about ":memory:" / path= local mode: it is a pure-Python re-implementation for
tests and prototypes. It searches EXACTLY and ignores HNSW, quantization and payload-index
settings (they are accepted and stored, nothing more). Every recall/latency number in
lesson 11 that is about HNSW or quantization must come from a real server.
"""

from __future__ import annotations

import uuid
import warnings
from typing import Any, Optional, Sequence

import numpy as np

from ..retrieval.base import Where
from ..types import CHUNK_META_KEYS, Chunk, Hit
from .base import METRICS, check_batch
from .filters import to_qdrant_filter

DEFAULT_PAYLOAD_INDEXES = {"doc_id": "keyword", "classification": "keyword", "department": "keyword",
                           "language": "keyword", "doc_type": "keyword"}
QUANTIZATIONS = (None, "scalar", "binary", "product", "turbo")
_NS = uuid.UUID("6f1d3b8e-2b8a-4c35-9a53-1e0b1c11a011")   # fixed namespace: stable ids everywhere


def _qdrant():
    try:
        from qdrant_client import QdrantClient, models  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError("QdrantVectorStore needs qdrant-client: "
                          "uv pip install -r labs/11-managed-vectors/requirements.txt") from exc
    return QdrantClient, models


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_NS, chunk_id))


def chunk_payload(c: Chunk) -> dict:
    p: dict[str, Any] = {k: v for k, v in c.meta.items() if v is not None}
    p.update({"doc_id": c.doc_id, "id": c.id, "index": c.index, "section": c.section,
              "n_tokens": c.n_tokens, "_chunk": c.to_dict()})
    return p


class QdrantVectorStore:
    def __init__(self, dim: Optional[int] = None, metric: str = "cosine", *,
                 client=None, url: Optional[str] = None, location: Optional[str] = None,
                 path: Optional[str] = None, api_key: Optional[str] = None,
                 collection: str = "ragkit", recreate: bool = False,
                 m: int = 16, ef_construct: int = 100, ef_search: Optional[int] = None,
                 full_scan_threshold: Optional[int] = None, on_disk: bool = False,
                 quantization: Optional[str] = None, rescore: bool = True,
                 oversampling: Optional[float] = None, exact: bool = False, acorn: bool = False,
                 payload_indexes: Optional[dict] = None, batch_size: int = 256):
        if metric not in METRICS:
            raise ValueError(f"metric must be one of {METRICS}")
        if quantization not in QUANTIZATIONS:
            raise ValueError(f"quantization must be one of {QUANTIZATIONS}")
        QdrantClient, self._m = _qdrant()
        if client is None:
            if url:
                client = QdrantClient(url=url, api_key=api_key)
            elif path:
                client = QdrantClient(path=path)
            else:
                client = QdrantClient(location=location or ":memory:")
        self.client = client
        self.dim, self.metric, self.collection = dim, metric, collection
        self.m_, self.ef_construct, self.full_scan_threshold, self.on_disk = (
            m, ef_construct, full_scan_threshold, on_disk)
        self.ef_search, self.exact, self.acorn = ef_search, exact, acorn
        self.quantization, self.rescore, self.oversampling = quantization, rescore, oversampling
        self.payload_indexes = DEFAULT_PAYLOAD_INDEXES if payload_indexes is None else payload_indexes
        self.batch_size = batch_size
        self.name = f"qdrant:{collection}"
        self.local = type(client).__name__ == "QdrantClient" and _is_local(client)
        if recreate and self.client.collection_exists(collection):
            self.client.delete_collection(collection)
        if self.client.collection_exists(collection):
            info = self.client.get_collection(collection)
            vp = info.config.params.vectors
            self.dim = getattr(vp, "size", self.dim)
        elif dim is not None:
            self._create(dim)

    # ------------------------------------------------------------------ schema
    @property
    def distance(self):
        d = self._m.Distance
        return {"cosine": d.COSINE, "dot": d.DOT, "l2": d.EUCLID}[self.metric]

    def quantization_config(self):
        m = self._m
        if self.quantization == "scalar":
            return m.ScalarQuantization(scalar=m.ScalarQuantizationConfig(
                type=m.ScalarType.INT8, quantile=0.99, always_ram=True))
        if self.quantization == "binary":
            return m.BinaryQuantization(binary=m.BinaryQuantizationConfig(always_ram=True))
        if self.quantization == "product":
            return m.ProductQuantization(product=m.ProductQuantizationConfig(
                compression=m.CompressionRatio.X16, always_ram=True))
        if self.quantization == "turbo":
            return m.TurboQuantization(turbo=m.TurboQuantQuantizationConfig(bits=m.TurboQuantBitSize.BITS4))
        return None

    def _create(self, dim: int) -> None:
        m = self._m
        hnsw = m.HnswConfigDiff(m=self.m_, ef_construct=self.ef_construct, on_disk=self.on_disk,
                                full_scan_threshold=self.full_scan_threshold)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")          # local mode warns that it ignores indexes
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=m.VectorParams(size=dim, distance=self.distance, on_disk=self.on_disk),
                hnsw_config=hnsw, quantization_config=self.quantization_config())
            for field, schema in self.payload_indexes.items():   # BEFORE data: filterable HNSW
                self.client.create_payload_index(self.collection, field_name=field, field_schema=schema)
        self.dim = dim

    # ------------------------------------------------------------------ contract
    def __len__(self) -> int:
        if not self.client.collection_exists(self.collection):
            return 0
        return self.client.count(self.collection, exact=True).count

    def add(self, chunks: Sequence[Chunk], vectors) -> None:
        chunks = list(chunks)
        if not chunks:
            return
        v = check_batch(chunks, vectors, self.dim)
        if self.dim is None or not self.client.collection_exists(self.collection):
            self._create(v.shape[1])
        P = self._m.PointStruct
        for i in range(0, len(chunks), self.batch_size):
            batch = [P(id=point_id(c.id), vector=row.tolist(), payload=chunk_payload(c))
                     for c, row in zip(chunks[i:i + self.batch_size], v[i:i + self.batch_size])]
            self.client.upsert(self.collection, points=batch, wait=True)

    def remove(self, doc_id: str) -> int:
        if not self.client.collection_exists(self.collection):
            return 0
        flt = to_qdrant_filter({"doc_id": doc_id})
        n = self.client.count(self.collection, count_filter=flt, exact=True).count
        if n:
            self.client.delete(self.collection, points_selector=self._m.FilterSelector(filter=flt),
                               wait=True)
        return n

    def search_params(self, *, ef: Optional[int] = None, exact: Optional[bool] = None):
        m = self._m
        q = None
        if self.quantization:
            q = m.QuantizationSearchParams(rescore=self.rescore, oversampling=self.oversampling)
        acorn = m.AcornSearchParams(enable=True) if self.acorn else None
        return m.SearchParams(hnsw_ef=ef if ef is not None else self.ef_search,
                              exact=self.exact if exact is None else exact,
                              quantization=q, acorn=acorn)

    def search(self, vector, k: int = 5, where: Where = None, *, ef: Optional[int] = None,
               exact: Optional[bool] = None) -> list[Hit]:
        if self.dim is None or not self.client.collection_exists(self.collection):
            return []
        q = np.asarray(vector, dtype=np.float32).reshape(-1)
        with warnings.catch_warnings():
            if self.local:                    # "local mode is exact": documented above
                warnings.simplefilter("ignore")
            res = self.client.query_points(
                self.collection, query=q.tolist(), limit=k, query_filter=to_qdrant_filter(where),
                search_params=self.search_params(ef=ef, exact=exact), with_payload=True)
        hits = []
        for i, p in enumerate(res.points):
            c = Chunk.from_dict(p.payload["_chunk"])
            s = float(p.score)
            if self.metric == "l2":
                s = -s * s                    # Qdrant returns the distance; ragkit: -squared distance
            hits.append(Hit(chunk=c, score=s, rank=i + 1, scores={"vector": s}, retriever=self.name))
        return hits

    # ------------------------------------------------------------------ operations
    def info(self) -> dict:
        """Collection status, point/segment counts, and the effective HNSW/quantization config."""
        i = self.client.get_collection(self.collection)
        hc = i.config.hnsw_config
        return {"status": str(getattr(i, "status", "")), "points": i.points_count,
                "indexed_vectors": getattr(i, "indexed_vectors_count", None),
                "segments": getattr(i, "segments_count", None),
                "m": getattr(hc, "m", None), "ef_construct": getattr(hc, "ef_construct", None),
                "quantization": self.quantization, "local_mode": self.local}

    def snapshot(self) -> Optional[str]:
        """Ask the server for a collection snapshot (a backup file on the server). Server only."""
        if self.local:
            raise RuntimeError("snapshots need a Qdrant server (local mode has none)")
        return self.client.create_snapshot(self.collection).name


def _is_local(client) -> bool:
    inner = getattr(client, "_client", None)
    return type(inner).__name__ == "QdrantLocal"


# Keys that a payload index could usefully cover (documentation for the lab).
FILTERABLE_KEYS = ("doc_id",) + tuple(k for k in CHUNK_META_KEYS if k not in ("title", "source_path"))

__all__ = ["QdrantVectorStore", "point_id", "chunk_payload", "QUANTIZATIONS", "DEFAULT_PAYLOAD_INDEXES"]
