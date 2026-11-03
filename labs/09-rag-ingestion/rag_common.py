"""Shared by rag_answer.py, rag_eval.py and long_context.py: the index and the "LLM"."""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llmkit import LLM, load_dotenv  # noqa: E402
from ragkit.acme import acme_chunks  # noqa: E402
from ragkit.chunking import make_chunker  # noqa: E402
from ragkit.fake import ExtractiveAnswerer  # noqa: E402
from ragkit.retrieval import BM25Index  # noqa: E402

DEFAULT_CHUNKER = "heading:400:40:150"
MODELS_HELP = ("extractive (free, offline: not a model, picks sentences) | mock:mock-model "
               "(needs `python -m mockllm` in another terminal) | anthropic:claude-haiku-5-5 (live)")


def build_index(chunker: str = DEFAULT_CHUNKER, tokenizer: str = "approx") -> BM25Index:
    idx = BM25Index()
    idx.add(acme_chunks(make_chunker(chunker, tokenizer)))
    return idx


def make_llm(spec: str):
    if spec == "extractive":
        return ExtractiveAnswerer()
    load_dotenv(str(ROOT / ".env"))
    return LLM(spec)


def is_paid(spec: str) -> bool:
    return not (spec == "extractive" or spec.startswith("mock"))
