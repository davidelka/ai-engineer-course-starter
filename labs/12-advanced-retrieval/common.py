"""Shared by the lesson 12 scripts: paths, chunks, retrievers, the offline/live LLM, reports."""

from __future__ import annotations

import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
for p in (str(ROOT), str(LAB)):
    if p not in sys.path:
        sys.path.insert(0, p)

from llmkit import LLM, load_dotenv  # noqa: E402
from ragkit.acme import acme_chunks, acme_qa  # noqa: E402
from ragkit.chunking import make_chunker  # noqa: E402
from ragkit.replay import dispatch, replay_llm  # noqa: E402
from ragkit.retrieval import BM25Index  # noqa: E402

RESULTS = LAB / "results"
FIXTURES = LAB / "fixtures"
REWRITE_FIXTURES = FIXTURES / "rewrites.jsonl"
# Reuse lesson 10's embedding cache: if you embedded Acme with e5-small there, nothing is
# embedded again here.
CACHE_DIR = ROOT / "labs" / "10-embeddings" / "results" / "cache"
DEFAULT_CHUNKER = "heading:400:40:150"   # lesson 9's baseline, same as lesson 10
DEFAULT_DENSE = "e5-small"
DEFAULT_LLM = "anthropic:claude-haiku-5-5"

DENSE_HELP = "e5-small (default, local) | bge-m3 | openai:text-embedding-3-small | fake (offline, lexical)"
LLM_HELP = ("replay (offline: hand-written/recorded rewrites + a lexical judge, $0) | "
            "anthropic:claude-haiku-5-5 (live, paid) | mock:mock-model (needs python -m mockllm)")


def chunks(chunker: str = DEFAULT_CHUNKER):
    return acme_chunks(make_chunker(chunker, "approx"))


def bm25_index(chunk_list=None) -> BM25Index:
    idx = BM25Index()
    idx.add(chunk_list if chunk_list is not None else chunks())
    return idx


def dense_index(spec: str, chunk_list=None):
    """DenseRetriever over the chunks. 'fake' is not cached (it is instant); real models use
    lesson 10's disk cache."""
    from ragkit.dense import DenseRetriever
    from ragkit.embed import CachedEmbedder, make_embedder
    t0 = time.perf_counter()
    if spec.startswith("openai:"):
        load_dotenv(str(ROOT / ".env"))
    emb = make_embedder(spec, cache_dir=None if spec.startswith("fake") else CACHE_DIR)
    if spec.startswith("fake"):
        print("note: dense model 'fake' is a hashing embedder (lexical, NOT semantic): it cannot "
              "find translations. Use it to test the plumbing; run with e5-small for real numbers.",
              file=sys.stderr)
    d = DenseRetriever(emb)
    d.add(chunk_list if chunk_list is not None else chunks())
    if isinstance(emb, CachedEmbedder):
        s = emb.stats
        print(f"[{spec}] {len(d)} chunks in {time.perf_counter() - t0:.1f}s "
              f"(cache hits {s['hits']}, embedded now {s['misses']})", file=sys.stderr)
    return d


def make_llm(spec: str) -> LLM:
    """'replay' -> the offline LLM (rewrite fixtures + lexical judge); anything else -> llmkit."""
    if spec == "replay":
        from ragkit.query import MARKER as RW, fixture_responder, load_rewrite_fixtures
        from ragkit.rerank.llm import MARKER as RR, overlap_responder
        fx = load_rewrite_fixtures(REWRITE_FIXTURES)
        extra = RESULTS / "rewrites_recorded.jsonl"      # your live recordings override the hand-written rows
        if extra.exists():
            fx.update(load_rewrite_fixtures(extra))
        print("note: LLM 'replay' answers offline. Rewrites come from fixtures/rewrites.jsonl "
              "(hand-written, NOT model output) or your recordings; the reranking 'judge' is "
              "lexical overlap. Costs shown are estimates of what Haiku would charge.", file=sys.stderr)
        return replay_llm(dispatch({RW: fixture_responder(fx), RR: overlap_responder},
                                   default=lambda body: "{}"))
    if not spec.startswith("mock"):
        load_dotenv(str(ROOT / ".env"))
    return LLM(spec)


def is_paid(spec: str) -> bool:
    return not (spec == "replay" or spec.startswith("mock") or spec.startswith("fake")
                or spec.startswith("ce:") or spec in ("e5-small", "e5-base", "bge-m3", "qwen3-0.6b"))


def confirm(prompt: str, yes: bool) -> bool:
    if yes:
        return True
    return input(f"{prompt} [y/N] ").strip().lower() == "y"


__all__ = ["LAB", "ROOT", "RESULTS", "FIXTURES", "REWRITE_FIXTURES", "CACHE_DIR", "DEFAULT_CHUNKER",
           "DEFAULT_DENSE", "DEFAULT_LLM", "DENSE_HELP", "LLM_HELP", "chunks", "bm25_index",
           "dense_index", "make_llm", "is_paid", "confirm", "acme_qa"]
