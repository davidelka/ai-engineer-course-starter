"""Shared by the lesson 13 scripts: paths, the two pipelines, generators, judges, saving runs."""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
for p in (str(ROOT), str(LAB)):
    if p not in sys.path:
        sys.path.insert(0, p)

from llmkit import LLM, load_dotenv  # noqa: E402
from ragkit.acme import acme_documents, acme_qa  # noqa: E402
from ragkit.chunking import make_chunker  # noqa: E402
from ragkit.diagnose import (case_from_trace, classify, heuristic_judge_llm, load_traces,  # noqa: E402
                             quote_status_map, run_diagnosis, save_traces)
from ragkit.retrieval import BM25Index  # noqa: E402

RESULTS = LAB / "results"
FIXTURES = LAB / "fixtures"
L12 = ROOT / "labs" / "12-advanced-retrieval"
REWRITE_FIXTURES = L12 / "fixtures" / "rewrites.jsonl"          # lesson 12's hand-written rewrites
REWRITE_RECORDED = L12 / "results" / "rewrites_recorded.jsonl"  # your live recordings, if you made them
CACHE_DIR = ROOT / "labs" / "10-embeddings" / "results" / "cache"
DEFAULT_CHUNKER = "heading:400:40:150"       # the lesson 9 baseline, same as lessons 10-12
DEFAULT_LIVE = "anthropic:claude-haiku-5-5"

PIPELINES = {
    "baseline": "lesson 9: BM25 alone, top 5 chunks into the prompt",
    "best": "lesson 12: BM25 + dense (RRF) + query rewrite (multi, decompose, translate) + version filter",
}
LLM_HELP = ("extractive (offline, $0: copies the best sentences, cannot reason) | rule (offline simulation that "
            "also obeys the version rule) | anthropic:claude-haiku-5-5 (live, paid) | mock:mock-model")
JUDGE_HELP = "heuristic (offline, lexical, $0) | none | anthropic:claude-haiku-5-5 (live, paid)"


def documents():
    return acme_documents()


def chunks(chunker: str = DEFAULT_CHUNKER):
    return make_chunker(chunker, "approx").split_all(documents())


def make_generator(spec: str):
    """The answering model. 'extractive' and 'rule' are free stand-ins (not language models)."""
    if spec == "extractive":
        from ragkit.fake import ExtractiveAnswerer
        return ExtractiveAnswerer()
    if spec == "rule":
        from evalkit.rag import RuleFollowingAnswerer
        return RuleFollowingAnswerer()
    if not spec.startswith("mock"):
        load_dotenv(str(ROOT / ".env"))
    return LLM(spec)


def make_judge(spec: str):
    if spec in ("none", ""):
        return None
    if spec == "heuristic":
        return heuristic_judge_llm()
    if not spec.startswith("mock"):
        load_dotenv(str(ROOT / ".env"))
    return LLM(spec)


def make_rewriter(spec: str):
    from ragkit.query import QueryRewriter, load_rewrite_fixtures, replay_rewriter
    if spec == "replay":
        fx = load_rewrite_fixtures(REWRITE_FIXTURES)
        fx.update(load_rewrite_fixtures(REWRITE_RECORDED))     # your live rewrites override the hand-written ones
        return replay_rewriter(fx)
    load_dotenv(str(ROOT / ".env"))
    return QueryRewriter(LLM(spec))


def build_retriever(pipeline: str, chunk_list, *, dense: str = "fake", rewriter: str = "replay",
                    reranker: str = ""):
    """baseline = BM25; best = VersionAware(Rewriting(Hybrid(BM25, dense))). reranker (optional)
    wraps the result in lesson 12's RerankingRetriever (fetch 30)."""
    bm25 = BM25Index()
    bm25.add(chunk_list)
    if pipeline == "baseline":
        r = bm25
    elif pipeline in ("best", "hybrid", "versions"):
        from ragkit.versions import VersionAwareRetriever
        if pipeline == "versions":          # BM25 + version filter only
            return _maybe_rerank(VersionAwareRetriever(bm25, mode="retrieved"), reranker)
        from ragkit.dense import DenseRetriever
        from ragkit.embed import make_embedder
        from ragkit.hybrid import HybridRetriever
        from ragkit.query import RewritingRetriever
        emb = make_embedder(dense, cache_dir=None if dense.startswith("fake") else CACHE_DIR)
        d = DenseRetriever(emb)
        d.add(chunk_list)
        hy = HybridRetriever({"bm25": bm25, "dense": d})
        rw = RewritingRetriever(hy, make_rewriter(rewriter), modes=("multi", "decompose", "translate"))
        r = rw if pipeline == "hybrid" else VersionAwareRetriever(rw, mode="retrieved")
    else:
        raise SystemExit(f"unknown pipeline {pipeline!r}; choose from {', '.join(PIPELINES)}")
    return _maybe_rerank(r, reranker)


def _maybe_rerank(r, reranker: str):
    if not reranker:
        return r
    from ragkit.rerank import RerankingRetriever, make_reranker
    return RerankingRetriever(r, make_reranker(reranker), fetch_k=30)


def is_paid(spec: str) -> bool:
    return bool(spec) and not (spec in ("extractive", "rule", "heuristic", "none", "replay", "fake")
                               or spec.startswith("mock") or spec.startswith("fake"))


def confirm(prompt: str, yes: bool) -> bool:
    if yes:
        return True
    return input(f"{prompt} [y/N] ").strip().lower() == "y"


def tag(*parts: str) -> str:
    return "_".join(p.replace(":", "-").replace("/", "-") for p in parts if p)


def diagnose_all(traces):
    return [classify(case_from_trace(t)) for t in traces]


def offline_note(llm: str, judge: str, dense: str = "", rewriter: str = "") -> str:
    fake = [x for x in (llm, judge, dense, rewriter) if x in ("extractive", "rule", "heuristic", "fake", "replay")]
    if not fake:
        return ""
    return ("note: OFFLINE components: " + ", ".join(fake) + ". 'extractive' copies sentences, so it never "
            "hallucinates and never combines two sources; 'heuristic' judges by word overlap; 'fake' dense is "
            "lexical; 'replay' rewrites were hand-written. The pipeline and the classifier are real; the numbers "
            "of the generation stages are not what Claude would score. Run live for those.")


__all__ = ["LAB", "ROOT", "RESULTS", "FIXTURES", "DEFAULT_CHUNKER", "DEFAULT_LIVE", "PIPELINES", "LLM_HELP",
           "JUDGE_HELP", "documents", "chunks", "make_generator", "make_judge", "make_rewriter", "build_retriever",
           "is_paid", "confirm", "tag", "diagnose_all", "offline_note", "acme_qa", "quote_status_map",
           "run_diagnosis", "save_traces", "load_traces"]
