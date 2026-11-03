"""Shared by the lesson-23 scripts: paths, the index, the answerers and judges, the dataset.

Answerer specs (--model):
  extractive         ragkit's ExtractiveAnswerer: free, offline, NOT a model; ignores the prompt
  rule               evalkit's RuleFollowingAnswerer: extractive + a SIMULATION of obeying the
                     "prefer the latest effective_date" rule when the prompt contains it
  mock:mock-model    the local mock server (python -m mockllm): checks plumbing and cost
                     accounting, answers are placeholders
  anthropic:claude-haiku-5-5   live
Judge specs (--judge):
  heuristic          evalkit's HeuristicJudgeLLM: free, lexical, NOT a model
  heuristic-biased   the same with a position bias (for the pairwise demo)
  mock:mock-model    mock server: returns the first valid value of each schema field
  anthropic:claude-haiku-5-5   live
"""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
for p in (str(ROOT), str(LAB)):
    if p not in sys.path:
        sys.path.insert(0, p)

from evalkit import HeuristicJudgeLLM, Judge, OutputCache, acme_golden  # noqa: E402
from evalkit.rag import RagSystem, RuleFollowingAnswerer  # noqa: E402
from llmkit import LLM, load_dotenv  # noqa: E402
from llmkit.pricing import PRICES  # noqa: E402
from ragkit.acme import acme_chunks  # noqa: E402
from ragkit.chunking import make_chunker  # noqa: E402
from ragkit.fake import ExtractiveAnswerer  # noqa: E402
from ragkit.retrieval import BM25Index  # noqa: E402

RESULTS = LAB / "results"
DATA = LAB / "data"
CHUNKER = "heading:400:40:150"          # the lesson-9 baseline
CACHE = RESULTS / "cache"


def build_index(chunker: str = CHUNKER) -> BM25Index:
    idx = BM25Index()
    idx.add(acme_chunks(make_chunker(chunker, "approx")))
    return idx


def make_answerer(spec: str):
    if spec == "extractive":
        return ExtractiveAnswerer()
    if spec == "rule":
        return RuleFollowingAnswerer()
    load_dotenv(str(ROOT / ".env"))
    return LLM(spec)


def make_judge(spec: str, cache: bool = True) -> Judge:
    if spec == "heuristic":
        llm = HeuristicJudgeLLM()
    elif spec == "heuristic-biased":
        llm = HeuristicJudgeLLM(position_bias=0.34)
    else:
        load_dotenv(str(ROOT / ".env"))
        llm = LLM(spec)
    return Judge(llm, cache=OutputCache(RESULTS / "judge_cache") if cache else None)


def is_paid(spec: str) -> bool:
    return not (spec in ("extractive", "rule") or spec.startswith("heuristic") or spec.startswith("mock"))


def confirm(spec: str, n_calls: int, tokens_per_call: int, out_tokens: int, yes: bool) -> bool:
    """Print a generous cost estimate for a paid run and ask; cached calls are free."""
    if not is_paid(spec):
        return True
    p = PRICES.get(spec.split(":", 1)[1], PRICES["claude-haiku-5-5"])
    est = n_calls * (tokens_per_call * p["input"] + out_tokens * p["output"]) / 1e6
    print(f"{n_calls} calls on {spec}: at most ${est:.3f} (generous estimate; cached calls cost nothing)")
    return yes or input("continue? [y/N] ").strip().lower() == "y"


def system_for(spec: str, prompt: str = "v1", k: int = 5, index=None) -> RagSystem:
    return RagSystem(index or build_index(), make_answerer(spec), prompt=prompt, k=k)


def progress(i: int, n: int, run) -> None:
    print(f"\r  {i}/{n}  cached {run.cached_count}  ${run.cost_usd:.4f}", end="" if i < n else "\n", file=sys.stderr)


__all__ = ["LAB", "ROOT", "RESULTS", "DATA", "CACHE", "build_index", "make_answerer", "make_judge", "is_paid",
           "confirm", "system_for", "progress", "acme_golden", "OutputCache"]
