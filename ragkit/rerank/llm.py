"""An LLM as reranker, with llmkit structured output (one call per question).

    rr = LLMReranker(LLM("anthropic:claude-haiku-5-5"))
    hits = rr.rerank(question, candidates, top_n=5)

The prompt lists the candidates as [1]..[n] (each cut to max_chars) and asks for a 0-10
relevance score for EVERY passage, as JSON validated by Pydantic. Scoring all passages in one
call ("listwise input, pointwise scores") is cheaper than one call per passage and lets the
model compare candidates; asking for a full permutation instead (RankGPT, Sun et al. 2023) is
fragile with 30 items: ids get skipped or repeated. Missing ids get -1, so they sink.

Trade-offs against a cross-encoder: no download, understands instructions ("prefer the
newest policy", "a proposal is not a decision"), handles Hebrew well; but 1-3 s of latency,
a per-query cost (30 passages x ~180 tokens ~ 6K input tokens ~ $0.0006 with Claude Haiku
5.5), and positional bias (passages early in the list get a boost: shuffle or keep the first
stage's order and measure). Scores are coarse (many ties): ties keep the first-stage order.

Offline: overlap_responder() is a lexical "judge" for ragkit.replay: it parses the passages
from the real prompt, scores them with OverlapReranker and answers in the schema. It tests
the plumbing (prompt, schema, parsing, cost accounting); it says nothing about Claude.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from llmkit import LLM
from llmkit.structured import complete_structured

from ..replay import body_text
from .base import BaseReranker
from .fake import OverlapReranker

MARKER = "ACME PASSAGE RERANKER"

SYSTEM = f"""{MARKER}
You judge search results for the internal knowledge base of Acme Ltd. For the question,
give EVERY numbered passage a relevance score from 0 to 10:
10 = contains the answer; 6-9 = partly answers or is needed together with another passage;
1-5 = same topic, no answer; 0 = unrelated.
A passage from a superseded policy version, or a meeting proposal that was not adopted, is
less relevant than the current policy. Judge only the text shown; do not answer the question.
Passages may be in English or Hebrew; the question may be in either language."""


class PassageScore(BaseModel):
    id: int = Field(description="The passage number shown in brackets.")
    score: int = Field(ge=0, le=10, description="Relevance from 0 to 10.")


class RerankJudgement(BaseModel):
    scores: list[PassageScore] = Field(description="One entry per passage, in any order.")


def build_prompt(query: str, texts: list[str]) -> str:
    lines = [f"Question: {query}", "", "Passages:"]
    for i, t in enumerate(texts, start=1):
        lines.append(f"[{i}] " + " ".join(t.split()))
    return "\n".join(lines)


class LLMReranker(BaseReranker):
    max_chars = 700

    def __init__(self, llm: LLM, *, max_chars: int = 700, max_tokens: int = 1200):
        super().__init__()
        self.llm, self.max_chars, self.max_tokens = llm, max_chars, max_tokens
        self.name = f"llm:{llm.model}"

    def score(self, query: str, texts: list[str]) -> list[float]:
        res = complete_structured(self.llm, build_prompt(query, texts), RerankJudgement, system=SYSTEM,
                                  max_tokens=self.max_tokens, max_repairs=1)
        scores = [-1.0] * len(texts)
        seen = set()
        for s in res.value.scores:
            if 1 <= s.id <= len(texts) and s.id not in seen:
                seen.add(s.id)
                scores[s.id - 1] = float(s.score)
        self.stats.calls = res.attempts
        self.stats.cost_usd = res.cost_usd
        self.stats.input_tokens, self.stats.output_tokens = res.input_tokens, res.output_tokens
        self.stats.estimated = getattr(self.llm, "api_key", "") == "replay"
        self.stats.extra = {"missing_ids": len(texts) - len(seen)}
        return scores


_P = re.compile(r"^\[(\d+)\] (.*)$", re.M)
_QL = re.compile(r"Question:\s*(.+)")


def overlap_responder(body: dict) -> str:
    """Offline judge for ragkit.replay: lexical overlap scaled to 0..10 integers."""
    _, user = body_text(body)
    q = (_QL.search(user).group(1).strip() if _QL.search(user) else "")
    items = [(int(m.group(1)), m.group(2)) for m in _P.finditer(user)]
    raw = OverlapReranker().score(q, [t for _, t in items]) if items else []
    top = max(raw) if raw else 1.0
    scores = [{"id": i, "score": int(round(10 * s / top)) if top > 0 else 0} for (i, _), s in zip(items, raw)]
    return RerankJudgement.model_validate({"scores": scores}).model_dump_json()


__all__ = ["LLMReranker", "RerankJudgement", "PassageScore", "SYSTEM", "MARKER", "build_prompt",
           "overlap_responder"]
