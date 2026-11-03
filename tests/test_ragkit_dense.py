"""Environment tests for lesson 10's ragkit modules: embed, vectors, dense, metrics.
Offline: the fake embedder, stub sentence-transformers model, httpx.MockTransport for OpenAI."""

import json

import pytest

np = pytest.importorskip("numpy")   # lesson 10 adds numpy to the requirements
import httpx  # noqa: E402

from ragkit.dense import DenseRetriever
from ragkit.embed import (CachedEmbedder, Embedder, HashingEmbedder, OpenAIEmbedder,
                          SentenceTransformerEmbedder, SqliteVectorCache, cache_key,
                          embed_with_cache, make_embedder)
from ragkit.metrics import hit_at_k, mean, recall_at_k, reciprocal_rank, run_queries, summarize
from ragkit.retrieval import BM25Index
from ragkit.retrieval.base import Index, Retriever
from ragkit.types import Chunk
from ragkit.vectors import (NumpyVectorStore, VectorStore, cosine_top_k, l2_normalize, make_store,
                            similarity, top_k, truncate_dims)


def ch(i, text, doc="d", **meta):
    return Chunk(id=f"{doc}#{i}", doc_id=doc, text=text, start=0, end=len(text), index=i,
                 meta={"title": doc, **meta})


# ------------------------------------------------------------------ vector math
def test_normalize_and_metrics_agree_on_unit_vectors():
    rng = np.random.default_rng(0)
    m = l2_normalize(rng.normal(size=(50, 16)))
    q = l2_normalize(rng.normal(size=16))[0]
    assert np.allclose(np.linalg.norm(m, axis=1), 1, atol=1e-5)
    rank = lambda s: list(np.argsort(-s, kind="stable"))
    assert rank(similarity(q, m, "cosine")) == rank(similarity(q, m, "dot")) == rank(similarity(q, m, "l2"))


def test_zero_vector_does_not_nan():
    z = l2_normalize(np.zeros((2, 4)))
    assert np.all(z == 0) and not np.isnan(z).any()


def test_top_k_ties_and_bounds():
    idx, sc = top_k([0.5, 0.9, 0.9, 0.1], 2)
    assert list(idx) == [1, 2] and np.allclose(sc, [0.9, 0.9])
    assert len(top_k([1.0, 2.0], 10)[0]) == 2
    assert len(top_k([], 3)[0]) == 0


def test_cosine_top_k_ignores_length():
    m = np.array([[10.0, 0.0], [0.6, 0.8], [0.0, 1.0]])
    idx, sc = cosine_top_k([1.0, 0.0], m, 2)
    assert list(idx) == [0, 1] and sc[0] == pytest.approx(1.0)


def test_truncate_dims_renormalizes():
    v = truncate_dims(np.arange(1, 9, dtype=float), 4)
    assert v.shape == (1, 4) and np.linalg.norm(v) == pytest.approx(1.0)


# ------------------------------------------------------------------ embedders
def test_fake_embedder_is_deterministic_and_normalized():
    a, b = HashingEmbedder(64), HashingEmbedder(64)
    va = a.embed_documents(["Up to 5 vacation days carry over", "חופשה שנתית"])
    vb = b.embed_documents(["Up to 5 vacation days carry over", "חופשה שנתית"])
    assert va.shape == (2, 64) and va.dtype == np.float32
    assert np.array_equal(va, vb)
    assert np.allclose(np.linalg.norm(va, axis=1), 1, atol=1e-5)
    assert isinstance(a, Embedder)
    q = a.embed_query("vacation days")
    assert float(q @ va[0]) > float(q @ va[1])


def test_make_embedder_specs():
    assert make_embedder("fake:32").dim == 32
    e5 = make_embedder("e5-small")
    assert e5.model_id.startswith("st:intfloat/multilingual-e5-small") and "query: " in e5.model_id
    oa = make_embedder("openai:text-embedding-3-small:256")
    assert oa.model_id == "openai:text-embedding-3-small:256" and oa.dim == 256
    with pytest.raises(ValueError):
        make_embedder("nope")


class StubST:
    """Stands in for sentence_transformers.SentenceTransformer (no download)."""

    def __init__(self):
        self.calls = []

    def encode(self, inputs, **kw):
        self.calls.append((list(inputs), kw))
        return l2_normalize(np.array([[len(t), 1.0, 0.0] for t in inputs]))


def test_sentence_transformer_prefixes_and_kwargs():
    stub = StubST()
    emb = SentenceTransformerEmbedder.preset("e5-small", model=stub, batch_size=8)
    emb.embed_documents(["a", "b", "c"])
    emb.embed_queries(["q"])
    (docs, kw1), (qs, kw2) = stub.calls
    assert docs == ["passage: a", "passage: b", "passage: c"] and qs == ["query: q"]
    assert kw1["normalize_embeddings"] is True and kw1["batch_size"] == 8
    assert "prompt_name" not in kw2
    qwen = SentenceTransformerEmbedder.preset("qwen3-0.6b", model=StubST())
    qwen.embed_queries(["x"])
    assert qwen.model.calls[0][1]["prompt_name"] == "query"


def _openai_transport(log):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        log.append({"auth": request.headers["authorization"].startswith("Bearer "), **body})
        n = len(body["input"])
        dim = body.get("dimensions", 8)
        data = [{"index": i, "embedding": [float(i + 1)] * dim, "object": "embedding"} for i in range(n)]
        return httpx.Response(200, json={"data": list(reversed(data)), "usage": {"prompt_tokens": 10 * n}})
    return httpx.MockTransport(handler)


def test_openai_embedder_batches_orders_and_costs():
    log = []
    emb = OpenAIEmbedder("text-embedding-3-small", dims=4, api_key="sk-test", batch_size=2,
                         transport=_openai_transport(log))
    v = emb.embed_documents(["a", "b", "c"])
    assert v.shape == (3, 4)
    assert [len(x["input"]) for x in log] == [2, 1] and all(x["dimensions"] == 4 for x in log)
    assert all(x["auth"] for x in log)
    assert np.allclose(np.linalg.norm(v, axis=1), 1)
    assert emb.tokens == 30 and emb.cost_usd == pytest.approx(30 * 0.02 / 1e6)


def test_openai_retries_429(monkeypatch):
    monkeypatch.setattr("ragkit.embed.openai.time.sleep", lambda s: None)
    state = {"n": 0}

    def handler(req):
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": "slow down"})
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 0.0]}], "usage": {"prompt_tokens": 1}})

    emb = OpenAIEmbedder(api_key="sk-test", transport=httpx.MockTransport(handler))
    assert emb.embed_queries(["x"]).shape == (1, 2) and state["n"] == 2


def test_openai_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIEmbedder(transport=_openai_transport([])).embed_documents(["x"])


# ------------------------------------------------------------------ cache
def test_cache_key_depends_on_model_kind_text():
    k = cache_key("m", "document", "t")
    assert len(k) == 64
    assert len({k, cache_key("m2", "document", "t"), cache_key("m", "query", "t"), cache_key("m", "document", "t2")}) == 4


def test_embed_with_cache_dedupes_and_calls_once():
    calls = []

    def fn(texts):
        calls.append(list(texts))
        return np.array([[len(t), 0.0] for t in texts], dtype=np.float32)

    cache = {}
    out = embed_with_cache(["aa", "b", "aa"], fn, cache, "m")
    assert calls == [["aa", "b"]] and out.shape == (3, 2) and out[0, 0] == out[2, 0] == 2
    embed_with_cache(["b", "ccc"], fn, cache, "m")
    assert calls[-1] == ["ccc"]


def test_cached_embedder_on_disk(tmp_path):
    inner = HashingEmbedder(32)
    emb = CachedEmbedder(inner, tmp_path)
    a = emb.embed_documents(["x", "y"])
    assert emb.stats == {"hits": 0, "misses": 2, "calls": 1}
    emb2 = CachedEmbedder(HashingEmbedder(32), tmp_path)        # a new process, same files
    b = emb2.embed_documents(["y", "x", "z"])
    assert emb2.stats == {"hits": 2, "misses": 1, "calls": 1}
    assert np.array_equal(a[0], b[1])
    emb2.embed_queries(["x"])                                   # queries are a different kind
    assert emb2.stats["misses"] == 2
    files = list(tmp_path.glob("*.sqlite"))
    assert len(files) == 1 and len(SqliteVectorCache(files[0])) == 4


# ------------------------------------------------------------------ stores
CHUNKS = [ch(0, "vacation carry over five days", "hr-vac", language="en", classification="internal"),
          ch(1, "parental leave sixteen weeks", "hr-par", language="en", classification="internal"),
          ch(2, "חופשה שנתית והעברת ימים", "hr-vac-he", language="he", classification="internal"),
          ch(3, "incident postmortem auth service", "eng-pm", language="en", classification="confidential")]


@pytest.mark.parametrize("spec", ["numpy", "faiss", "faiss:HNSW8"])
def test_store_contract(spec):
    if spec.startswith("faiss"):
        pytest.importorskip("faiss")
    emb = HashingEmbedder(64)
    store = make_store(spec)
    assert isinstance(store, VectorStore)
    store.add(CHUNKS, emb.embed_documents([c.text for c in CHUNKS]))
    assert len(store) == 4
    q = emb.embed_query("vacation days carry over")
    hits = store.search(q, k=2)
    assert hits[0].chunk.id == "hr-vac#0" and hits[0].rank == 1 and "vector" in hits[0].scores
    assert hits[0].score >= hits[1].score
    hits = store.search(q, k=5, where={"classification": ["internal"]})
    assert len(hits) == 3 and all(h.chunk.classification == "internal" for h in hits)
    assert [h.chunk.id for h in store.search(q, k=5, where={"language": "he"})] == ["hr-vac-he#2"]
    assert store.remove("hr-vac") == 1 and len(store) == 3
    assert all(h.chunk.doc_id != "hr-vac" for h in store.search(q, k=5))
    store.add([CHUNKS[1]], emb.embed_documents(["vacation carry over"]))     # upsert by id
    assert len(store) == 3 and store.search(q, k=1)[0].chunk.id == "hr-par#1"


def test_store_rejects_dim_mismatch_and_nan():
    s = NumpyVectorStore()
    s.add(CHUNKS[:1], np.ones((1, 4)))
    with pytest.raises(ValueError):
        s.add(CHUNKS[1:2], np.ones((1, 5)))
    with pytest.raises(ValueError):
        s.add(CHUNKS[1:2], np.array([[np.nan, 0, 0, 0]]))


def test_faiss_filter_uses_selector_for_large_sets():
    faiss = pytest.importorskip("faiss")  # noqa: F841
    from ragkit.vectors import FaissVectorStore
    rng = np.random.default_rng(1)
    chunks = [ch(i, f"t{i}", f"d{i % 7}", lang="he" if i % 2 else "en") for i in range(300)]
    vecs = rng.normal(size=(300, 16)).astype(np.float32)
    s = FaissVectorStore(index="Flat", brute_force_below=10)
    s.add(chunks, vecs)
    exact = NumpyVectorStore()
    exact.add(chunks, vecs)
    where = {"lang": "he"}
    a = [h.chunk.id for h in s.search(vecs[3], 10, where)]
    b = [h.chunk.id for h in exact.search(vecs[3], 10, where)]
    assert a == b and a[0] == "d3#3"


def test_numpy_store_save_load(tmp_path):
    emb = HashingEmbedder(32)
    s = NumpyVectorStore()
    s.add(CHUNKS, emb.embed_documents([c.text for c in CHUNKS]))
    s.save(tmp_path / "st")
    t = NumpyVectorStore.load(tmp_path / "st")
    q = emb.embed_query("parental leave")
    assert [h.chunk.id for h in s.search(q, 3)] == [h.chunk.id for h in t.search(q, 3)]


# ------------------------------------------------------------------ dense retriever
def test_dense_retriever_is_an_index_and_uses_context_text():
    seen = []

    class Spy(HashingEmbedder):
        def _embed(self, texts, kind):
            seen.append((kind, list(texts)))
            return super()._embed(texts, kind)

    d = DenseRetriever(Spy(64))
    assert isinstance(d, Retriever) and isinstance(d, Index)
    d.add(CHUNKS)
    assert seen[0][0] == "document" and seen[0][1][0].startswith("hr-vac\n")
    hits = d.search("parental leave weeks", k=2)
    assert seen[-1][0] == "query" and hits[0].chunk.doc_id == "hr-par"
    assert hits[0].retriever.startswith("dense:fake")
    assert d.remove("hr-par") == 1 and len(d) == 3


def test_dense_retriever_in_ingest_pipeline(tmp_path):
    from ragkit.pipeline import IngestPipeline
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("---\ntitle: Vacation\nlanguage: en\n---\n# Vacation\nUp to 5 days carry over.\n")
    (docs / "b.md").write_text("---\ntitle: Parking\nlanguage: en\n---\n# Parking\nBook a spot by 18:00.\n")
    dense = DenseRetriever(CachedEmbedder(HashingEmbedder(64), tmp_path / "cache"))
    pipe = IngestPipeline(tmp_path / "store", chunker="heading:200:0", index=dense)
    pipe.run(docs)
    assert pipe.index.search("carry over days", k=1)[0].chunk.doc_id == "a"
    before = dense.embedder.stats["misses"]
    (docs / "b.md").write_text("---\ntitle: Parking\nlanguage: en\n---\n# Parking\nBook a spot by 17:00.\n")
    pipe.run(docs)
    assert dense.embedder.stats["misses"] - before == 1     # only the edited chunk was embedded
    assert len(dense) == 2


# ------------------------------------------------------------------ metrics
def test_ranking_metrics():
    ranked = ["x", "a", "x", "b", "c"]
    assert recall_at_k(ranked, ["a", "b"], 2) == 0.5        # doc ranking: x, a, b, c
    assert recall_at_k(ranked, ["a", "b"], 3) == 1.0
    assert hit_at_k(ranked, ["c"], 3) == 0.0 and hit_at_k(ranked, ["c"], 4) == 1.0
    assert reciprocal_rank(ranked, ["b"]) == pytest.approx(1 / 3)
    assert reciprocal_rank(ranked, ["zz"]) == 0.0
    assert reciprocal_rank(ranked, ["c"], k=3) == 0.0
    assert mean([]) == 0.0
    with pytest.raises(ValueError):
        recall_at_k(ranked, [], 5)


def test_metrics_on_golden_set_with_bm25():
    from ragkit.acme import acme_chunks, acme_qa
    idx = BM25Index()
    idx.add(acme_chunks("heading:400:40:150"))
    qa = acme_qa()
    res = run_queries(idx, qa, depth=10)
    assert len(res) == sum(1 for q in qa if q["source_ids"])
    table = summarize(res)
    assert {"ALL", "hebrew", "multi_hop", "cross-lingual"} <= set(table)
    assert table["cross-lingual"]["n"] == 6
    assert 0.8 < table["ALL"]["recall@10"] <= 1.0
    assert table["cross-lingual"]["recall@5"] < table["ALL"]["recall@5"]   # lesson 9's finding
