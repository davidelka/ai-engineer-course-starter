"""Lesson 11: managed vector stores (Qdrant, pgvector, S3 Vectors), filters, bench, sizing.

Runs offline. Qdrant tests use qdrant-client's in-process ":memory:" mode (skipped if
qdrant-client is not installed). pgvector SQL is tested as pure functions and with a fake
connection; live databases are tested only when an env var points at one:
    RAGKIT_TEST_PG_DSN       any PostgreSQL (filters -> SQL semantics on a jsonb table)
    RAGKIT_TEST_PGVECTOR_DSN PostgreSQL with the vector extension (full PgVectorStore)
    RAGKIT_TEST_QDRANT_URL   a Qdrant server (HNSW + quantization + filters, real index)
"""

from __future__ import annotations

import json
import os
import uuid

import numpy as np
import pytest

from ragkit.types import Chunk
from ragkit.vectors import NumpyVectorStore, VectorStore
from ragkit.vectors.bench import (exact_filtered_top_k, filtered_recall, pareto_frontier, post_filter,
                                  recall_ids, sweep, synth_clustered, violations)
from ragkit.vectors.filters import (ROLES, acl_where, as_callable, matches_ext, to_s3vectors_filter,
                                    to_sql_where)
from ragkit.vectors.pgvector_store import (PgVectorStore, index_sql, schema_sql, search_sql, session_sql,
                                           to_score, vector_literal)
from ragkit.vectors.s3vectors_store import S3VectorsStore
from ragkit.vectors.sizing import (compare, graph_bytes_per_node, hnsw_ram_bytes, s3vectors_monthly)


def mk(i, doc, **meta):
    return Chunk(id=f"{doc}#{i}", doc_id=doc, text=f"text {doc} {i}", start=0, end=1, index=i, meta=meta)


@pytest.fixture(scope="module")
def corpus():
    rng = np.random.default_rng(0)
    chunks = []
    for d in range(30):
        cls = ["public", "internal", "internal", "confidential"][d % 4]
        dept = ["engineering", "hr", "finance", "sales_support", "company"][d % 5]
        for i in range(4):
            chunks.append(mk(i, f"doc{d:02d}", classification=cls, department=dept,
                             language="he" if d % 6 == 0 else "en",
                             effective_date=f"2026-{(d % 12) + 1:02d}-01", tags=["a", f"t{d % 3}"]))
    vecs = rng.normal(size=(len(chunks), 24)).astype(np.float32)
    return chunks, vecs


WHERES = [None, {"language": "he"}, {"classification": ["public", "internal"]},
          {"effective_date": {"$gte": "2026-06-01", "$lt": "2026-10-01"}}, {"doc_id": "doc03"},
          {"classification": {"$ne": "internal"}}, {"department": {"$nin": ["hr", "finance"]}},
          {"tags": {"$contains": "t1"}}, {"$or": [{"language": "he"}, {"department": "hr"}]},
          {"$and": [{"language": "en"}, {"$or": [{"classification": "confidential"}, {"doc_id": "doc01"}]}]},
          {"classification": []}, {"$or": []}] + [acl_where(r) for r in ROLES]


# ------------------------------------------------------------------ filters
def test_matches_ext_is_a_superset_of_matches(corpus):
    from ragkit.retrieval.base import matches
    chunks, _ = corpus
    for w in [None, {"language": "he"}, {"classification": ["public"]}, {"effective_date": {"$gte": "2026-05-01"}}]:
        assert [matches(c, w) for c in chunks] == [matches_ext(c, w) for c in chunks]


def test_unknown_operators_fail_closed(corpus):
    c = corpus[0][0]
    for bad in ({"classification": {"$regex": "x"}}, {"$not": [{"a": 1}]}):
        with pytest.raises(ValueError):
            matches_ext(c, bad)
        with pytest.raises(ValueError):
            to_sql_where(bad)
        with pytest.raises(ValueError):
            to_s3vectors_filter(bad)


def test_acl_where_matrix():
    def chunk(cls, dept):
        return mk(0, "d", classification=cls, department=dept)
    assert matches_ext(chunk("confidential", "engineering"), acl_where("engineering"))
    assert not matches_ext(chunk("confidential", "hr"), acl_where("engineering"))
    assert matches_ext(chunk("confidential", "hr"), acl_where("security"))
    assert not matches_ext(chunk("internal", "hr"), acl_where("contractor"))
    assert matches_ext(chunk("public", "hr"), acl_where("contractor"))
    assert not matches_ext(chunk("public", "hr"), acl_where("nobody"))
    assert not matches_ext(chunk("restricted", "hr"), acl_where("security"))


def test_sql_where_binds_values_and_rejects_unsafe_keys():
    sql, params = to_sql_where({"language": "he", "classification": ["a", "b"], "n": {"$gte": 3}})
    assert "he" not in sql and params == ["he", ["a", "b"], 3]
    assert "(meta->>'n')::numeric >= %s" in sql
    with pytest.raises(ValueError):
        to_sql_where({"x'; DROP TABLE t; --": 1})
    assert to_sql_where(None) == ("TRUE", [])
    assert to_sql_where({"classification": []})[0] == "FALSE"


def test_s3vectors_filter_shape():
    assert to_s3vectors_filter({"genre": "scifi"}) == {"genre": {"$eq": "scifi"}}
    f = to_s3vectors_filter(acl_where("engineering"))
    assert f == {"$or": [{"classification": {"$in": ["public", "internal"]}},
                         {"$and": [{"classification": {"$eq": "confidential"}},
                                   {"department": {"$eq": "engineering"}}]}]}
    assert to_s3vectors_filter(None) is None


@pytest.mark.skipif(not os.environ.get("RAGKIT_TEST_PG_DSN"), reason="set RAGKIT_TEST_PG_DSN for a live PostgreSQL")
def test_sql_where_semantics_on_live_postgres(corpus):
    psycopg = pytest.importorskip("psycopg")
    chunks, _ = corpus
    with psycopg.connect(os.environ["RAGKIT_TEST_PG_DSN"]) as cn, cn.cursor() as cur:
        cur.execute("CREATE TEMP TABLE t (id text PRIMARY KEY, doc_id text, meta jsonb)")
        cur.executemany("INSERT INTO t VALUES (%s, %s, %s::jsonb)",
                        [(c.id, c.doc_id, json.dumps(c.meta)) for c in chunks])
        for w in WHERES:
            sql, params = to_sql_where(w)
            cur.execute(f"SELECT id FROM t WHERE {sql}", params)
            assert sorted(r[0] for r in cur.fetchall()) == sorted(c.id for c in chunks if matches_ext(c, w)), w


# ------------------------------------------------------------------ Qdrant (in-process)
@pytest.fixture()
def qstore(corpus):
    pytest.importorskip("qdrant_client")
    from ragkit.vectors.qdrant_store import QdrantVectorStore
    chunks, vecs = corpus
    s = QdrantVectorStore(collection=f"t{uuid.uuid4().hex[:8]}", m=16, ef_construct=64, quantization="scalar")
    s.add(chunks, vecs)
    return s


def test_qdrant_is_a_vector_store(qstore, corpus):
    assert isinstance(qstore, VectorStore)
    assert len(qstore) == len(corpus[0]) and qstore.dim == 24 and qstore.local


@pytest.mark.parametrize("w", WHERES, ids=lambda w: str(w)[:40])
def test_qdrant_matches_exact_numpy(qstore, corpus, w):
    chunks, vecs = corpus
    ref = NumpyVectorStore()
    ref.add(chunks, vecs)
    q = vecs[5] + 0.1
    got = qstore.search(q, k=10, where=w)
    want = ref.search(q, k=10, where=as_callable(w))
    assert [h.chunk.id for h in got] == [h.chunk.id for h in want]
    assert np.allclose([h.score for h in got], [h.score for h in want], atol=1e-4)
    assert all(matches_ext(h.chunk, w) for h in got)
    assert all(h.scores["vector"] == h.score and h.rank == i + 1 for i, h in enumerate(got))


def test_qdrant_upsert_and_remove(qstore, corpus):
    chunks, vecs = corpus
    qstore.add(chunks[:4], vecs[:4] * -1)                        # same ids: replaced, not added
    assert len(qstore) == len(chunks)
    top = qstore.search(-vecs[0], k=1)[0]
    assert top.chunk.id == chunks[0].id
    assert qstore.remove("doc00") == 4 and len(qstore) == len(chunks) - 4
    assert qstore.remove("doc00") == 0
    assert all(h.chunk.doc_id != "doc00" for h in qstore.search(-vecs[0], k=20))


def test_qdrant_roundtrips_chunks_and_metrics(corpus):
    pytest.importorskip("qdrant_client")
    from ragkit.vectors.qdrant_store import QdrantVectorStore
    chunks, vecs = corpus
    for metric in ("dot", "l2"):
        s = QdrantVectorStore(metric=metric, collection=f"m{metric}")
        s.add(chunks, vecs)
        ref = NumpyVectorStore(metric=metric)
        ref.add(chunks, vecs)
        got, want = s.search(vecs[3], 5), ref.search(vecs[3], 5)
        assert [h.chunk.id for h in got] == [h.chunk.id for h in want]
        assert np.allclose([h.score for h in got], [h.score for h in want], rtol=1e-3, atol=1e-3)
    assert got[0].chunk == chunks[3]                          # payload carries the whole chunk


def test_qdrant_with_dense_retriever(corpus):
    pytest.importorskip("qdrant_client")
    from ragkit.dense import DenseRetriever
    from ragkit.embed import HashingEmbedder
    from ragkit.vectors.qdrant_store import QdrantVectorStore
    chunks, _ = corpus
    d = DenseRetriever(HashingEmbedder(dim=64), store=QdrantVectorStore(collection="dense"))
    d.add(chunks)
    hits = d.search("text doc07", k=3, where={"language": "en"})
    assert hits and hits[0].retriever.startswith("dense:") and all(h.chunk.language == "en" for h in hits)


def test_qdrant_config_objects():
    pytest.importorskip("qdrant_client")
    from ragkit.vectors.qdrant_store import QdrantVectorStore, point_id
    for q in ("scalar", "binary", "product", "turbo"):
        s = QdrantVectorStore(quantization=q, oversampling=2.0, acorn=True, ef_search=128, collection=f"q{q}")
        assert s.quantization_config() is not None
        p = s.search_params()
        assert p.hnsw_ef == 128 and p.quantization.rescore and p.quantization.oversampling == 2.0 and p.acorn.enable
    assert point_id("a#1") == point_id("a#1") != point_id("a#2")
    with pytest.raises(ValueError):
        QdrantVectorStore(quantization="pq")


@pytest.mark.skipif(not os.environ.get("RAGKIT_TEST_QDRANT_URL"), reason="set RAGKIT_TEST_QDRANT_URL for a live Qdrant")
def test_qdrant_live_server(corpus):
    from ragkit.vectors.qdrant_store import QdrantVectorStore
    chunks, vecs = corpus
    s = QdrantVectorStore(url=os.environ["RAGKIT_TEST_QDRANT_URL"], collection="ragkit_pytest", recreate=True,
                          quantization="scalar", oversampling=2.0)
    try:
        s.add(chunks, vecs)
        assert not s.local and len(s) == len(chunks)
        exact = [h.chunk.id for h in s.search(vecs[1], 10, exact=True)]
        assert [h.chunk.id for h in s.search(vecs[1], 10, where=None)][:3] == exact[:3]
        assert all(h.chunk.language == "he" for h in s.search(vecs[1], 10, where={"language": "he"}))
    finally:
        s.client.delete_collection("ragkit_pytest")


# ------------------------------------------------------------------ pgvector (pure SQL + fake connection)
def test_pgvector_sql_builders():
    assert any("vector(384)" in s for s in schema_sql("acme", 384))
    assert any("halfvec(384)" in s for s in schema_sql("acme", 384, halfvec=True))
    assert "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)" in index_sql("acme")
    assert "vector_ip_ops" in index_sql("acme", "dot") and "lists = 50" in index_sql("acme", kind="ivfflat", lists=50)
    assert "halfvec_l2_ops" in index_sql("acme", "l2", halfvec=True)
    assert index_sql("acme", kind=None) is None
    assert session_sql(ef_search=100, iterative_scan="relaxed_order", max_scan_tuples=5000) == [
        "SET LOCAL hnsw.ef_search = 100", "SET LOCAL hnsw.iterative_scan = relaxed_order",
        "SET LOCAL hnsw.max_scan_tuples = 5000"]
    sql, params = search_sql("acme", "cosine", 10, {"language": "he"})
    assert sql.count("<=>") == 2 and "LIMIT 10" in sql and params == ["Q", "he", "Q"]
    with pytest.raises(ValueError):
        schema_sql("acme; DROP", 3)
    with pytest.raises(ValueError):
        session_sql(iterative_scan="sometimes")
    assert to_score(0.25, "cosine") == 0.75 and to_score(-3.0, "dot") == 3.0 and to_score(2.0, "l2") == -4.0
    assert vector_literal([1, 0.5]) == "[1.0,0.5]"


class FakeCursor:
    def __init__(self, conn):
        self.conn, self.rowcount, self._rows = conn, 0, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.log.append((sql, params))
        if sql.startswith("SELECT chunk"):
            self._rows = [(json.dumps(c.to_dict()), 0.1 * i) for i, c in enumerate(self.conn.rows[:3])]
        elif sql.startswith("SELECT count"):
            self._rows = [(len(self.conn.rows),)]
        elif sql.startswith("DELETE"):
            self.rowcount = 2

    def executemany(self, sql, rows):
        self.conn.log.append((sql, list(rows)))

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0]


class FakeConn:
    def __init__(self, rows):
        self.rows, self.log, self.commits = rows, [], 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


def test_pgvector_store_with_fake_connection(corpus):
    chunks, vecs = corpus
    conn = FakeConn(chunks)
    s = PgVectorStore(conn=conn, table="acme", ef_search=80, iterative_scan="relaxed_order")
    assert isinstance(s, VectorStore) and len(s) == 0
    s.add(chunks[:5], vecs[:5])
    sqls = [x[0] for x in conn.log]
    assert any(q.startswith("CREATE TABLE IF NOT EXISTS acme") for q in sqls)
    assert any("USING hnsw" in q for q in sqls)
    insert = next(x for x in conn.log if x[0].startswith("INSERT"))
    assert "ON CONFLICT (id) DO UPDATE" in insert[0] and len(insert[1]) == 5
    assert insert[1][0][4].startswith("[") and json.loads(insert[1][0][3])["id"] == chunks[0].id
    hits = s.search(vecs[0], k=3, where=acl_where("engineering"))
    sets = [x[0] for x in conn.log if x[0].startswith("SET LOCAL")]
    assert sets == ["SET LOCAL hnsw.ef_search = 80", "SET LOCAL hnsw.iterative_scan = relaxed_order"]
    q = conn.log[-1]
    assert q[1][0] == q[1][-1] == vector_literal(vecs[0]) and "OR" in q[0]
    assert [h.chunk.id for h in hits] == [c.id for c in chunks[:3]]
    assert np.allclose([h.score for h in hits], [1.0, 0.9, 0.8])
    assert s.remove("doc00") == 2 and len(s) == len(chunks)
    with pytest.raises(ValueError):
        PgVectorStore()


@pytest.mark.skipif(not os.environ.get("RAGKIT_TEST_PGVECTOR_DSN"), reason="set RAGKIT_TEST_PGVECTOR_DSN (pgvector)")
def test_pgvector_live(corpus):
    chunks, vecs = corpus
    s = PgVectorStore(os.environ["RAGKIT_TEST_PGVECTOR_DSN"], table="ragkit_pytest", recreate=True,
                      iterative_scan="relaxed_order")
    try:
        s.add(chunks, vecs)
        ref = NumpyVectorStore()
        ref.add(chunks, vecs)
        for w in WHERES:
            got = [h.chunk.id for h in s.search(vecs[2], 5, w, exact=True)]
            assert got == [h.chunk.id for h in ref.search(vecs[2], 5, as_callable(w))], w
        assert s.remove("doc01") == 4 and len(s) == len(chunks) - 4
    finally:
        s._exec(["DROP TABLE IF EXISTS ragkit_pytest"])


# ------------------------------------------------------------------ S3 Vectors (fake boto3 client)
class FakeS3Vectors:
    """In-memory stand-in for boto3.client("s3vectors"): exact search, ENHANCED-mode filters."""

    def __init__(self):
        self.idx, self.calls = {}, []

    def create_vector_bucket(self, **kw):
        self.calls.append(("create_vector_bucket", kw))

    def create_index(self, **kw):
        self.calls.append(("create_index", kw))

    def put_vectors(self, vectorBucketName, indexName, vectors):
        assert len(vectors) <= 500
        for v in vectors:
            self.idx[v["key"]] = v

    def list_vectors(self, vectorBucketName, indexName, maxResults, nextToken=None, returnMetadata=False):
        keys = sorted(self.idx)
        start = int(nextToken or 0)
        page = keys[start:start + maxResults]
        out = {"vectors": [{"key": k, **({"metadata": self.idx[k]["metadata"]} if returnMetadata else {})}
                           for k in page]}
        if start + maxResults < len(keys):
            out["nextToken"] = str(start + maxResults)
        return out

    def delete_vectors(self, vectorBucketName, indexName, keys):
        for k in keys:
            self.idx.pop(k, None)

    def _ok(self, md, f):
        if f is None:
            return True
        for key, cond in f.items():
            if key == "$and":
                if not all(self._ok(md, x) for x in cond):
                    return False
            elif key == "$or":
                if not any(self._ok(md, x) for x in cond):
                    return False
            else:
                v = md.get(key)
                for op, arg in cond.items():
                    ok = {"$eq": lambda: v == arg or (isinstance(v, list) and arg in v),
                          "$ne": lambda: v != arg, "$in": lambda: v in arg, "$nin": lambda: v not in arg,
                          "$gte": lambda: v is not None and v >= arg, "$gt": lambda: v is not None and v > arg,
                          "$lte": lambda: v is not None and v <= arg, "$lt": lambda: v is not None and v < arg}[op]()
                    if not ok:
                        return False
        return True

    def query_vectors(self, vectorBucketName, indexName, queryVector, topK, returnDistance, returnMetadata,
                      filter=None, nextToken=None):
        q = np.asarray(queryVector["float32"])
        q = q / np.linalg.norm(q)
        rows = [(1 - float(np.dot(q, np.asarray(v["data"]["float32"]) / np.linalg.norm(v["data"]["float32"]))), k)
                for k, v in self.idx.items() if self._ok(v["metadata"], filter)]
        rows.sort()
        start = int(nextToken or 0)
        page = rows[start:min(start + 100, topK)]
        out = {"vectors": [{"key": k, "distance": d, "metadata": self.idx[k]["metadata"]} for d, k in page]}
        if start + 100 < min(topK, len(rows)):
            out["nextToken"] = str(start + 100)
        return out


def test_s3vectors_store_with_fake_client(corpus):
    chunks, vecs = corpus
    big = [mk(i, f"big{i // 4}", classification="internal", language="en") for i in range(1200)]
    bigv = np.random.default_rng(1).normal(size=(1200, 24)).astype(np.float32)
    fake = FakeS3Vectors()
    s = S3VectorsStore(fake, bucket="b", index="i", dim=24)
    s.create_index()
    assert fake.calls[1][1]["metadataConfiguration"] == {"nonFilterableMetadataKeys": ["chunk"]}
    s.add(chunks + big, np.vstack([vecs, bigv]))                  # > 500: batched
    assert len(s) == len(chunks) + 1200
    ref = NumpyVectorStore()
    ref.add(chunks + big, np.vstack([vecs, bigv]))
    for w in [None, {"language": "he"}, acl_where("engineering"), acl_where("contractor"),
              {"effective_date": {"$gte": "2026-06-01"}}]:
        got = s.search(vecs[7], k=10, where=w)
        assert [h.chunk.id for h in got] == [h.chunk.id for h in ref.search(vecs[7], 10, as_callable(w))]
    assert len(s.search(vecs[7], k=250)) == 250                   # paginated: 100 per page
    assert s.remove("doc02") == 4 and len(s) == len(chunks) + 1196
    with pytest.raises(ValueError):
        S3VectorsStore(fake, "b", "i", metric="dot")


# ------------------------------------------------------------------ bench + sizing
def test_bench_helpers():
    assert recall_ids([1, 2, 9], [1, 2, 3], 3) == pytest.approx(2 / 3)
    assert pareto_frontier([(1.0, 0.8), (2.0, 0.95), (1.5, 0.7), (3.0, 0.95), (4.0, 0.99)]) == [0, 1, 4]
    m = np.array([[1, 0], [0, 1], [0.9, 0.1], [-1, 0]], dtype=float)
    assert list(exact_filtered_top_k([1, 0], m, [False, True, True, True], 2)) == [2, 1]
    assert filtered_recall([5, 7], [5, 7, 9], 10) == pytest.approx(2 / 3)
    assert post_filter([0, 1, 2, 3], [False, True, False, True], 1) == [1]
    assert violations([0, 1], [False, True]) == 1
    x = synth_clustered(200, 16, clusters=5)
    assert x.shape == (200, 16) and np.allclose(np.linalg.norm(x, axis=1), 1, atol=1e-5)
    rows = sweep(lambda q, k, p: list(range(k)), x[:5], [list(range(10))] * 5, [1, 2], k=10, warmup=1)
    assert [r["param"] for r in rows] == [1, 2] and rows[0]["recall"] == 1.0


def test_faiss_hnsw_sweep_monotone():
    faiss = pytest.importorskip("faiss")
    from ragkit.vectors.bench import exact_top_k_matrix
    x = synth_clustered(3000, 32, clusters=40, seed=2)
    q = synth_clustered(50, 32, clusters=40, seed=3)
    truth = exact_top_k_matrix(q, x, 10)
    idx = faiss.IndexHNSWFlat(32, 8, faiss.METRIC_INNER_PRODUCT)
    idx.add(x)

    def search(v, k, ef):
        idx.hnsw.efSearch = ef
        return idx.search(v.reshape(1, -1), k)[1][0]
    rows = sweep(search, q, truth, [10, 40, 160], k=10)
    rec = [r["recall"] for r in rows]
    assert rec[0] <= rec[1] <= rec[2] and rec[2] > 0.95


def test_sizing_numbers():
    assert graph_bytes_per_node(16) == pytest.approx(132 + 68 / 15)
    r = hnsw_ram_bytes(1_000_000, 384)
    assert r["total_ram"] == pytest.approx(1.536e9 + 1e6 * (132 + 68 / 15))
    b = hnsw_ram_bytes(1_000_000, 384, quantization="binary")
    assert b["originals_disk"] == 1.536e9 and b["quantized_ram"] == 48e6
    s = s3vectors_monthly(10_000_000, 1024, 1_000_000, filterable_md=0, nonfilterable_md=0)
    assert 70 < s["queries"] < 90          # ~ the AWS Builder Center worked example (~$80)
    names = [x["option"] for x in compare(1_000_000, 1024, 100_000)]
    assert any("S3 Vectors" in n for n in names) and any("OpenSearch" in n for n in names)
