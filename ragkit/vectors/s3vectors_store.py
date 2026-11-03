"""S3VectorsStore: the VectorStore contract on Amazon S3 Vectors (lesson 11, the AWS option).

    import boto3
    store = S3VectorsStore(boto3.client("s3vectors", region_name="eu-central-1"),
                           bucket="acme-brain-vectors", index="acme-chunks-e5", dim=384)
    dense = DenseRetriever(embedder, store=store)

S3 Vectors (GA December 2025) is a bucket type with a vector API: PutVectors, QueryVectors,
DeleteVectors, ListVectors, GetVectors. You pay for storage (per GB-month), PUTs (per GB)
and queries (per call + per TB of index "processed"), and nothing while idle. There is no
HNSW knob: AWS chooses the index; the docs promise 90%+ average recall and sub-second cold
queries (~100 ms warm). Limits used below (AWS docs, November 2026): 500 vectors per
PutVectors/DeleteVectors call, 100 results per QueryVectors page (topK up to 10,000 with
pagination), 1-4,096 dimensions, metadata <= 40 KB per vector of which <= 2 KB filterable,
<= 10 non-filterable keys per index, distance "cosine" or "euclidean" (no dot product).

Filtering: indexes created in buckets made on/after 2026-09-30 default to the ENHANCED mode
(the filter is resolved first, then only matching vectors are searched: pre-filtering).
Older CLASSIC indexes evaluate the filter DURING the search and may return fewer than topK
results when few vectors match. `update-index-mode --index-mode ENHANCED` switches in place.

How chunks are stored
- key = chunk.id ("doc#3"); filterable metadata = doc_id + the ragkit filter keys
  (classification, department, language, doc_type, effective_date, version);
  non-filterable metadata "chunk" = the chunk as JSON (title, text, offsets) so a hit can be
  rebuilt without a second database. Create the index with
  metadataConfiguration={"nonFilterableMetadataKeys": ["chunk"]} (see create_index()).
- remove(doc_id): S3 Vectors has no delete-by-filter, so we list keys with that doc_id
  (ListVectors returns metadata) and delete them in batches of 500.

`client` is a boto3 "s3vectors" client, or any object with the same methods (the tests
use an in-memory fake). boto3 is NOT a ragkit dependency.
"""

from __future__ import annotations

import json
from typing import Optional, Sequence

import numpy as np

from ..retrieval.base import Where
from ..types import Chunk, Hit
from .base import METRICS, check_batch
from .filters import to_s3vectors_filter

FILTERABLE = ("doc_id", "classification", "department", "language", "doc_type", "effective_date",
              "version")
PUT_BATCH = 500
PAGE = 100
DISTANCE = {"cosine": "cosine", "l2": "euclidean"}


class S3VectorsStore:
    def __init__(self, client, bucket: str, index: str, dim: Optional[int] = None,
                 metric: str = "cosine", *, filterable: Sequence[str] = FILTERABLE):
        if metric not in METRICS:
            raise ValueError(f"metric must be one of {METRICS}")
        if metric not in DISTANCE:
            raise ValueError("S3 Vectors supports cosine and euclidean distance only (no dot)")
        self.client, self.bucket, self.index = client, bucket, index
        self.dim, self.metric, self.filterable = dim, metric, tuple(filterable)
        self.name = f"s3vectors:{bucket}/{index}"

    # ------------------------------------------------------------------ provisioning
    def create_index(self, dim: Optional[int] = None) -> None:
        """Create the vector bucket (if missing) and the index. Costs nothing until data arrives."""
        dim = dim or self.dim
        if not dim:
            raise ValueError("create_index needs dim")
        try:
            self.client.create_vector_bucket(vectorBucketName=self.bucket)
        except Exception as exc:                     # already exists -> fine
            if "Conflict" not in type(exc).__name__ and "exist" not in str(exc).lower():
                raise
        self.client.create_index(vectorBucketName=self.bucket, indexName=self.index,
                                 dataType="float32", dimension=int(dim),
                                 distanceMetric=DISTANCE[self.metric],
                                 metadataConfiguration={"nonFilterableMetadataKeys": ["chunk"]})
        self.dim = dim

    def teardown(self) -> None:
        """Delete the index, then the (now empty) bucket. Storage billing stops here."""
        self.client.delete_index(vectorBucketName=self.bucket, indexName=self.index)
        try:
            self.client.delete_vector_bucket(vectorBucketName=self.bucket)
        except Exception:                             # other indexes still in the bucket
            pass

    # ------------------------------------------------------------------ contract
    def _metadata(self, c: Chunk) -> dict:
        md = {k: c.meta.get(k) for k in self.filterable if k != "doc_id" and c.meta.get(k) is not None}
        md["doc_id"] = c.doc_id
        md["chunk"] = json.dumps(c.to_dict(), ensure_ascii=False)
        return md

    def add(self, chunks: Sequence[Chunk], vectors) -> None:
        chunks = list(chunks)
        if not chunks:
            return
        v = check_batch(chunks, vectors, self.dim)
        self.dim = v.shape[1]
        for i in range(0, len(chunks), PUT_BATCH):
            batch = [{"key": c.id, "data": {"float32": row.astype(np.float32).tolist()},
                      "metadata": self._metadata(c)}
                     for c, row in zip(chunks[i:i + PUT_BATCH], v[i:i + PUT_BATCH])]
            self.client.put_vectors(vectorBucketName=self.bucket, indexName=self.index, vectors=batch)

    def _keys_of(self, doc_id: str) -> list[str]:
        keys, token = [], None
        while True:
            kw = dict(vectorBucketName=self.bucket, indexName=self.index, returnMetadata=True,
                      maxResults=1000)
            if token:
                kw["nextToken"] = token
            page = self.client.list_vectors(**kw)
            keys += [x["key"] for x in page.get("vectors", [])
                     if (x.get("metadata") or {}).get("doc_id") == doc_id]
            token = page.get("nextToken")
            if not token:
                return keys

    def remove(self, doc_id: str) -> int:
        keys = self._keys_of(doc_id)
        for i in range(0, len(keys), PUT_BATCH):
            self.client.delete_vectors(vectorBucketName=self.bucket, indexName=self.index,
                                       keys=keys[i:i + PUT_BATCH])
        return len(keys)

    def __len__(self) -> int:
        n, token = 0, None
        while True:
            kw = dict(vectorBucketName=self.bucket, indexName=self.index, maxResults=1000)
            if token:
                kw["nextToken"] = token
            page = self.client.list_vectors(**kw)
            n += len(page.get("vectors", []))
            token = page.get("nextToken")
            if not token:
                return n

    def search(self, vector, k: int = 5, where: Where = None) -> list[Hit]:
        q = np.asarray(vector, dtype=np.float32).reshape(-1)
        kw = dict(vectorBucketName=self.bucket, indexName=self.index, queryVector={"float32": q.tolist()},
                  topK=int(k), returnDistance=True, returnMetadata=True)
        flt = to_s3vectors_filter(where)
        if flt is not None:
            kw["filter"] = flt
        out, token = [], None
        while True:
            resp = self.client.query_vectors(**kw, **({"nextToken": token} if token else {}))
            out += resp.get("vectors", [])
            token = resp.get("nextToken")
            if not token or len(out) >= k:
                break
        hits = []
        for i, x in enumerate(out[:k]):
            c = Chunk.from_dict(json.loads(x["metadata"]["chunk"]))
            d = float(x.get("distance", 0.0))
            s = 1.0 - d if self.metric == "cosine" else -d * d
            hits.append(Hit(chunk=c, score=s, rank=i + 1, scores={"vector": s}, retriever=self.name))
        return hits


__all__ = ["S3VectorsStore", "FILTERABLE"]
