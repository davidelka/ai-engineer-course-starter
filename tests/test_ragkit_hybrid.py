"""Environment tests for lesson 12's ragkit modules: fusion, hybrid, versions, query rewriting,
rerankers, ablation. Offline: fake embedder, replayed LLM (httpx.MockTransport behind a real
llmkit.LLM), a stub cross-encoder and a mocked Cohere endpoint."""

import json

import pytest

np = pytest.importorskip("numpy")   # the dense retriever (lesson 10) needs numpy
import httpx  # noqa: E402

from ragkit import fusion  # noqa: E402
from ragkit.ablation import evaluate_stage, format_stage, uses_replay  # noqa: E402
from ragkit.hybrid import HybridRetriever, fuse_hits  # noqa: E402
from ragkit.query import (QueryRewrite, QueryRewriter, RewritingRetriever, fixture_responder,  # noqa: E402
                          queries_for, replay_rewriter)
from ragkit.replay import dispatch, replay_llm  # noqa: E402
from ragkit.rerank import (CohereReranker, CrossEncoderReranker, LLMReranker, OverlapReranker,  # noqa: E402
                           RerankingRetriever, make_reranker)
from ragkit.rerank.llm import MARKER as RR_MARKER, overlap_responder  # noqa: E402
from ragkit.retrieval import BM25Index  # noqa: E402
from ragkit.retrieval.base import Index, Retriever  # noqa: E402
from ragkit.types import Chunk, Hit  # noqa: E402
from ragkit.versions import (VersionAwareRetriever, boost_recent, drop_superseded, stale_at_k,  # noqa: E402
                             supersedes_map)


def ch(doc, text, i=0, **meta):
    return Chunk(id=f"{doc}#{i}", doc_id=doc, text=text, start=0, end=len(text), index=i,
                 meta={"title": doc, **meta})


def hit(doc, rank, i=0, **meta):
    return Hit(chunk=ch(doc, doc, i, **meta), score=1.0 / rank, rank=rank, scores={"x": 1.0 / rank})


class Fixed:
    """A retriever that returns a fixed ranking (for fusion tests)."""

    def __init__(self, chunks, name, score=lambda i: 10.0 - i):
        self.chunks, self.name, self.score = chunks, name, score

    def search(self, query, k=5, where=None):
        return [Hit(chunk=c, score=self.score(i), rank=i + 1, scores={self.name: self.score(i)}, retriever=self.name)
                for i, c in enumerate(self.chunks[:k])]


TOY = [ch("vac-2024", "Up to 3 unused vacation days may be carried over until February 28.", effective_date="2024-01-01"),
       ch("vac-2026", "Up to 5 unused vacation days may be carried over until March 31.", effective_date="2026-01-01",
          supersedes="vac-2024"),
       ch("vac-2026-he", "עד 5 ימי חופשה שלא נוצלו אפשר להעביר עד 31 במרץ.", effective_date="2026-01-01",
          supersedes="vac-2024", language="he"),
       ch("parking", "The Tel Aviv parking garage closes at 22:00.", effective_date="2025-05-01"),
       ch("region", "Primary region il-central-1, failover to eu-central-1.", effective_date="2025-01-01")]


# ------------------------------------------------------------------ fusion
def test_rrf_formula_missing_and_weights():
    out = fusion.rrf([["a", "b", "c"], ["c", "a"]], k=60)
    assert [d for d, _ in out] == ["a", "c", "b"]
    assert dict(out)["b"] == pytest.approx(1 / 62)
    assert dict(fusion.rrf([["a"], ["b"]], weights=[1, 3]))["b"] == pytest.approx(3 / 61)
    with pytest.raises(ValueError):
        fusion.rrf([["a"]], weights=[1, 2])


def test_rrf_ties_are_deterministic_and_order_independent():
    a, b = ["x", "y", "z"], ["z", "y", "x"]
    assert fusion.rrf([a, b]) == fusion.rrf([b, a])
    out = fusion.rrf([["p", "q"], ["q", "p"]])
    assert [d for d, _ in out] == ["p", "q"] and out[0][1] == out[1][1]


def test_minmax_zscore_and_weighted_pitfall():
    assert fusion.minmax({"a": 4, "b": 2, "c": 0}) == {"a": 1.0, "b": 0.5, "c": 0.0}
    assert fusion.minmax({"a": 7}) == {"a": 1.0}
    z = fusion.zscore({"a": 1.0, "b": 3.0})
    assert z["a"] == pytest.approx(-1.0) and z["b"] == pytest.approx(1.0)
    out = dict(fusion.weighted_fusion([{"a": 10, "b": 5, "c": 0}, {"b": 0.9, "c": 0.8}], [0.5, 0.5]))
    assert out["c"] == 0.0 and out["b"] == pytest.approx(0.75)   # c's dense rank 2 became 0
    assert fusion.weighted_fusion([{"a": 1.0}], normalize="none") == [("a", 1.0)]


# ------------------------------------------------------------------ hybrid
def test_fuse_hits_keeps_every_stage_score():
    a = Fixed(TOY[:3], "bm25")
    b = Fixed([TOY[2], TOY[3]], "vector", score=lambda i: 0.9 - i / 10)
    out = fuse_hits({"bm25": a.search("q"), "dense": b.search("q")})
    top = {h.chunk.id: h for h in out}
    h = top["vac-2026-he#0"]
    assert h.scores["bm25"] == 8.0 and h.scores["vector"] == 0.9
    assert h.scores["rank:bm25"] == 3 and h.scores["rank:dense"] == 1 and "rrf" in h.scores
    assert out[0].chunk.id == "vac-2026-he#0"      # 3rd + 1st beats 1st alone with k=60
    assert [x.rank for x in out] == list(range(1, len(out) + 1))


def test_hybrid_is_a_retriever_and_index_and_k_does_not_change_order():
    from ragkit.dense import DenseRetriever
    from ragkit.embed import make_embedder
    bm, dn = BM25Index(), DenseRetriever(make_embedder("fake"))
    hy = HybridRetriever({"bm25": bm, "dense": dn}, fetch_k=10)
    assert isinstance(hy, Retriever) and isinstance(hy, Index)
    hy.add(TOY)
    assert len(bm) == len(dn) == len(TOY)
    five = [h.chunk.id for h in hy.search("unused vacation days carried over", k=5)]
    two = [h.chunk.id for h in hy.search("unused vacation days carried over", k=2)]
    assert five[:2] == two
    assert set(hy.last_timing) == {"bm25", "dense", "fusion"}
    assert hy.remove("parking") == 1 and len(bm) == len(TOY) - 1
    w = HybridRetriever({"bm25": bm, "dense": dn}, method="weighted", weights=[0.5, 0.5])
    assert w.search("il-central-1", k=1)[0].chunk.doc_id == "region"
    assert "fused" in w.search("il-central-1", k=1)[0].scores


# ------------------------------------------------------------------ versions
def test_supersedes_map_and_drop_modes():
    smap = supersedes_map(TOY)
    assert smap == {"vac-2024": {"vac-2026", "vac-2026-he"}}
    hits = [Hit(chunk=c, score=1.0, rank=i + 1) for i, c in enumerate([TOY[0], TOY[3], TOY[1]])]
    assert [h.chunk.doc_id for h in drop_superseded(hits)] == ["parking", "vac-2026"]
    only_old = [Hit(chunk=TOY[0], score=1.0, rank=1), Hit(chunk=TOY[3], score=0.5, rank=2)]
    assert [h.chunk.doc_id for h in drop_superseded(only_old)] == ["vac-2024", "parking"]   # kept
    assert [h.chunk.doc_id for h in drop_superseded(only_old, superseded_by=smap)] == ["parking"]
    assert [h.rank for h in drop_superseded(hits)] == [1, 2]
    assert hits[2].rank == 3                                  # inputs untouched


def test_drop_with_chain_in_corpus_map_and_cycle():
    hs = [hit("A", 1), hit("X", 2)]
    assert [h.chunk.doc_id for h in drop_superseded(hs, superseded_by={"A": ["B"], "B": ["C"]})] == ["X"]
    cyc = [hit("p", 1, supersedes="q"), hit("q", 2, supersedes="p"), hit("r", 3)]
    assert "r" in [h.chunk.doc_id for h in drop_superseded(cyc)]


def test_boost_recent_prefers_newer_and_records_score():
    hs = [Hit(chunk=TOY[0], score=1.0, rank=1), Hit(chunk=TOY[1], score=0.95, rank=2)]
    out = boost_recent(hs, weight=0.5)
    assert out[0].chunk.doc_id == "vac-2026" and "recency" in out[0].scores
    assert boost_recent(hs, weight=0.0)[0].chunk.doc_id == "vac-2024"


def test_version_aware_retriever_and_stale_metric():
    base = Fixed([TOY[0], TOY[1], TOY[3]], "bm25")
    v = VersionAwareRetriever(base)
    assert [h.chunk.doc_id for h in v.search("q", k=5)] == ["vac-2026", "parking"]
    assert "versions" in v.last_timing
    with pytest.raises(ValueError):
        VersionAwareRetriever(base, mode="corpus")
    q = {"tags": ["stale:vac-2024"]}
    assert stale_at_k(["vac-2024", "vac-2026"], q, 5) == 1.0
    assert stale_at_k(["vac-2026", "a", "b", "c", "d", "vac-2024"], q, 5) == 0.0


# ------------------------------------------------------------------ query rewriting
FX = {"How many vacation days carry over?": {
    "language": "en", "translation": "כמה ימי חופשה עוברים?", "variants": ["vacation rollover", "vacation rollover"],
    "subquestions": ["What is the carry-over limit?"], "step_back": "What is the vacation policy?",
    "hypothetical_answer": "Up to N days may be carried over."}}


def test_queries_for_order_dedupe_and_modes():
    rw = QueryRewrite.model_validate(FX["How many vacation days carry over?"])
    qs = queries_for("How many vacation days carry over?", rw, ("multi", "translate", "hyde"))
    assert [label for label, _ in qs] == ["original", "variant1", "translation", "hyde"]   # duplicate variant dropped
    with pytest.raises(ValueError):
        queries_for("q", rw, ("nope",))


def test_replay_rewriter_runs_the_real_structured_path():
    rw = replay_rewriter(FX)
    r = rw.rewrite("How many vacation days carry over?")
    assert r.value.translation == "כמה ימי חופשה עוברים?" and r.input_tokens > 100 and r.cost_usd > 0
    again = rw.rewrite("How many vacation days carry over?")
    assert again.cached and again.cost_usd == r.cost_usd and rw.calls == 1
    unknown = rw.rewrite("כמה חניות יש?")
    assert unknown.value.language == "he" and unknown.value.variants == []


def test_rewriter_fails_open_on_invalid_json():
    rw = QueryRewriter(replay_llm(lambda body: "not json at all"))
    r = rw.rewrite("anything")
    assert r.error and r.value.variants == [] and r.cost_usd > 0


def test_rewriting_retriever_filters_translation_by_language():
    seen = []

    class Spy:
        name = "spy"

        def search(self, query, k=5, where=None):
            seen.append((query, where))
            return [Hit(chunk=c, score=1.0, rank=i + 1) for i, c in enumerate(TOY[:3])]

    r = RewritingRetriever(Spy(), replay_rewriter(FX), modes=("translate",))
    out = r.search("How many vacation days carry over?", k=2)
    assert len(out) == 2 and r.last_cost > 0
    assert seen[0] == ("How many vacation days carry over?", None)
    assert seen[1] == ("כמה ימי חופשה עוברים?", {"language": "he"})
    r2 = RewritingRetriever(Spy(), replay_rewriter(FX), modes=("translate",), translation_filter=False)
    r2.search("How many vacation days carry over?")
    assert seen[-1][1] is None


def test_fixture_file_covers_answerable_golden_questions():
    from pathlib import Path
    from ragkit.acme import acme_qa
    from ragkit.query import load_rewrite_fixtures
    fx = load_rewrite_fixtures(Path(__file__).resolve().parents[1] / "labs/12-advanced-retrieval/fixtures/rewrites.jsonl")
    answerable = [q["question"] for q in acme_qa() if q["source_ids"]]
    assert all(q in fx for q in answerable)
    for rw in fx.values():
        QueryRewrite.model_validate(rw)


# ------------------------------------------------------------------ rerankers
def test_overlap_reranker_orders_and_keeps_scores():
    hs = [Hit(chunk=c, score=1.0, rank=i + 1, scores={"rrf": 0.1}) for i, c in enumerate(TOY)]
    out = OverlapReranker().rerank("where is il-central-1 failover", hs, top_n=2)
    assert out[0].chunk.doc_id == "region" and len(out) == 2
    assert out[0].scores["rrf"] == 0.1 and "rerank" in out[0].scores and out[0].scores["first_stage_rank"] == 5


def test_cross_encoder_with_stub_model():
    class Stub:
        def __init__(self):
            self.pairs = None

        def predict(self, pairs, batch_size=16, show_progress_bar=False):
            self.pairs = pairs
            return [len(p[1]) % 7 - 3.0 for p in pairs]     # logits, any scale
    stub = Stub()
    rr = CrossEncoderReranker.preset("bge-m3", model=stub)
    assert rr.model_name == "BAAI/bge-reranker-v2-m3" and rr.name == "ce:bge-reranker-v2-m3"
    hs = [Hit(chunk=c, score=1.0, rank=i + 1) for i, c in enumerate(TOY)]
    out = rr.rerank("q", hs)
    assert stub.pairs[0][0] == "q" and stub.pairs[0][1].startswith("vac-2024\n")   # context_text
    assert [h.score for h in out] == sorted([h.score for h in out], reverse=True)


def test_ties_keep_first_stage_order():
    class Flat(OverlapReranker):
        def score(self, query, texts):
            return [1.0] * len(texts)
    hs = [Hit(chunk=c, score=1.0, rank=i + 1) for i, c in enumerate(TOY)]
    assert [h.chunk.id for h in Flat().rerank("q", hs)] == [c.id for c in TOY]


def test_cohere_reranker_over_mock_transport():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        body = json.loads(req.content)
        assert body["model"] == "rerank-v5.0-fast" and len(body["documents"]) == 3
        return httpx.Response(200, json={"results": [{"index": 2, "relevance_score": 0.9},
                                                     {"index": 0, "relevance_score": 0.2}],
                                         "meta": {"billed_units": {"input_tokens": 500}}})
    rr = CohereReranker("rerank-v5.0-fast", api_key="test", http=httpx.Client(transport=httpx.MockTransport(handler)))
    hs = [Hit(chunk=c, score=1.0, rank=i + 1) for i, c in enumerate(TOY[:3])]
    out = rr.rerank("q", hs)
    assert calls[-1].headers["authorization"] == "Bearer test" and len(calls) == 2
    assert [h.chunk.id for h in out] == [TOY[2].id, TOY[0].id, TOY[1].id]   # unscored doc sinks
    assert rr.stats.cost_usd == pytest.approx(500 * 0.02 / 1e6)
    with pytest.raises(RuntimeError):
        CohereReranker(api_key="").rerank("q", hs)


def test_llm_reranker_through_replay():
    llm = replay_llm(overlap_responder)
    rr = LLMReranker(llm)
    hs = [Hit(chunk=c, score=1.0, rank=i + 1) for i, c in enumerate(TOY)]
    out = rr.rerank("parking garage Tel Aviv", hs, top_n=3)
    assert out[0].chunk.doc_id == "parking"
    assert rr.stats.cost_usd > 0 and rr.stats.estimated and rr.stats.extra["missing_ids"] == 0

    partial = LLMReranker(replay_llm(lambda body: json.dumps({"scores": [{"id": 2, "score": 9}]})))
    out = partial.rerank("q", hs)
    assert out[0].chunk.id == TOY[1].id and out[-1].score == -1.0


def test_reranking_retriever_tail_and_make_reranker():
    base = Fixed(TOY, "bm25")
    r = RerankingRetriever(base, OverlapReranker(), fetch_k=2)
    out = r.search("il-central-1", k=4)
    assert len(out) == 4 and [h.rank for h in out] == [1, 2, 3, 4]
    assert "rerank" in out[0].scores and "rerank" not in out[2].scores    # tail not reranked
    assert "rerank" in r.last_timing
    assert isinstance(make_reranker("fake"), OverlapReranker)
    assert make_reranker("ce:mmarco").model_name.startswith("cross-encoder/mmarco")
    assert make_reranker("cohere").model == "rerank-v4.0-fast"
    assert isinstance(make_reranker("llm:replay"), LLMReranker)
    with pytest.raises(ValueError):
        make_reranker("nope")


def test_dispatch_routes_by_marker():
    fx_resp = fixture_responder(FX)
    llm = replay_llm(dispatch({RR_MARKER: overlap_responder, "ACME QUERY REWRITER": fx_resp}, default=lambda b: "{}"))
    assert QueryRewriter(llm).rewrite("How many vacation days carry over?").value.step_back
    assert LLMReranker(llm).rerank("parking", [Hit(chunk=TOY[3], score=1, rank=1)])[0].score >= 0


# ------------------------------------------------------------------ ablation + golden set
def test_evaluate_stage_and_format():
    qa = [{"id": "t1", "type": "version_conflict", "question": "vacation carry over",
           "source_ids": ["vac-2026"], "tags": ["stale:vac-2024"]},
          {"id": "t2", "type": "single_hop", "question": "x", "source_ids": ["parking"]},
          {"id": "t3", "type": "unanswerable", "question": "y", "source_ids": []}]
    base = Fixed([TOY[0], TOY[1], TOY[3]], "bm25")
    rep = evaluate_stage("raw", base, qa)
    assert rep.table["ALL"]["n"] == 2 and rep.stale5 == 1.0 and len(rep.latency_ms) == 2
    rep2 = evaluate_stage("filtered", VersionAwareRetriever(base), qa)
    assert rep2.stale5 == 0.0 and rep2.get("version_conflict", "mrr") == 1.0
    text = format_stage(rep2, prev=rep)
    assert "stale doc in the top 5: 0/1" in text and "(+0.500)" in text
    assert not uses_replay(base)
    assert uses_replay(RerankingRetriever(base, make_reranker("llm:replay")))


@pytest.fixture(scope="module")
def acme():
    from ragkit.acme import acme_chunks, acme_qa
    from ragkit.chunking import make_chunker
    from ragkit.dense import DenseRetriever
    from ragkit.embed import make_embedder
    cs = acme_chunks(make_chunker("heading:400:40:150", "approx"))
    bm = BM25Index()
    bm.add(cs)
    dn = DenseRetriever(make_embedder("fake"))
    dn.add(cs)
    return cs, acme_qa(), bm, dn


def test_golden_version_filter_removes_stale_documents(acme):
    cs, qa, bm, dn = acme
    hy = HybridRetriever({"bm25": bm, "dense": dn})
    raw, filt = evaluate_stage("rrf", hy, qa), evaluate_stage("rrf+v", VersionAwareRetriever(hy), qa)
    assert raw.stale5 >= 0.6 and filt.stale5 <= 0.2
    assert filt.get("version_conflict", "mrr") > raw.get("version_conflict", "mrr")
    assert filt.get("ALL", "recall@5") >= raw.get("ALL", "recall@5") - 1e-9


def test_golden_translation_rewrite_fixes_bm25_cross_lingual(acme):
    from pathlib import Path
    cs, qa, bm, dn = acme
    rw = replay_rewriter(Path(__file__).resolve().parents[1] / "labs/12-advanced-retrieval/fixtures/rewrites.jsonl")
    base = evaluate_stage("bm25", bm, qa)
    tr = evaluate_stage("bm25+translate", RewritingRetriever(bm, rw, modes=("translate",)), qa)
    assert base.get("cross-lingual", "recall@5") < 0.5 < tr.get("cross-lingual", "recall@5")
