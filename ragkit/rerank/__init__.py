"""Rerankers (lesson 12): second-stage scoring of a first stage's candidates.

    from ragkit.rerank import make_reranker, RerankingRetriever
    rr = make_reranker("ce:bge-m3")                 # local cross-encoder, Apache-2.0, ~2.3 GB
    rr = make_reranker("cohere:rerank-v4.0-fast")   # hosted, COHERE_API_KEY
    rr = make_reranker("llm:anthropic:claude-haiku-5-5")
    rr = make_reranker("fake")                      # offline, lexical, NOT a model
    smart = RerankingRetriever(hybrid, rr, fetch_k=30)

Specs: fake | ce:bge-m3 | ce:mmarco | ce:<hf id> | cohere[:model] | llm:<llmkit spec>.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import BaseReranker, Reranker, RerankingRetriever, RerankStats
from .cohere import CohereReranker
from .cross_encoder import PRESETS, CrossEncoderReranker
from .fake import OverlapReranker
from .llm import LLMReranker, overlap_responder

RERANKER_HELP = ("fake (offline, lexical, NOT a model) | ce:bge-m3 | ce:mmarco | ce:<hf id> | "
                 "cohere[:rerank-v4.0-fast] | llm:anthropic:claude-haiku-5-5 | llm:replay")


def make_reranker(spec: str = "fake", *, llm: Optional[Any] = None, **kw) -> BaseReranker:
    kind, _, rest = spec.partition(":")
    if kind == "fake":
        return OverlapReranker(**kw)
    if kind == "ce":
        return CrossEncoderReranker.preset(rest, **kw) if rest in PRESETS else CrossEncoderReranker(rest, **kw)
    if kind == "cohere":
        return CohereReranker(rest or "rerank-v4.0-fast", **kw)
    if kind == "llm":
        if llm is None:
            if rest == "replay":
                from ..replay import replay_llm
                llm = replay_llm(overlap_responder)
            else:
                from llmkit import LLM
                llm = LLM(rest)
        return LLMReranker(llm, **kw)
    raise ValueError(f"unknown reranker {spec!r}. Known: {RERANKER_HELP}")


__all__ = ["Reranker", "BaseReranker", "RerankStats", "RerankingRetriever", "OverlapReranker",
           "CrossEncoderReranker", "PRESETS", "CohereReranker", "LLMReranker", "make_reranker",
           "RERANKER_HELP"]
