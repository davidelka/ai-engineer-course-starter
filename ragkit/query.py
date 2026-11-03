"""Query rewriting (lesson 12): one LLM call turns a question into better search queries.

    from ragkit.query import QueryRewriter, RewritingRetriever
    rw = QueryRewriter(LLM("anthropic:claude-haiku-5-5"))
    plan = rw.rewrite("Which team owns the service that caused the August outage?").value
    plan.subquestions   # ["What caused the August 2026 flow-api outage?", "Which team owns auth-service?"]
    smart = RewritingRetriever(hybrid, rw, modes=("multi", "decompose", "translate"))
    hits = smart.search(question, k=5)     # every query searched, results fused with RRF

The user's question is often a bad search query. Five standard rewrites, each aimed at a
specific failure, all produced by ONE structured-output call (llmkit.structured):

- multi       2-3 paraphrases ("multi-query", RAG-Fusion): the document may use other words
              ("carry over" vs "roll over" vs "transfer"). Helps recall a little, everywhere.
- decompose   2-3 self-contained sub-questions for multi-hop questions: "who owns the service
              that caused X" needs the postmortem AND the service catalog, and no single query
              is close to both.
- translate   the question in the corpus's other language (English <-> Hebrew): fixes the
              cross-lingual failure of BM25 directly, and helps dense models too.
- stepback    a more general question ("What is the parental leave policy?"): retrieves the
              section the specific answer lives in.
- hyde        a hypothetical answer passage (Gao et al. 2022): search with what an answer
              LOOKS like, which is closer to documents than a question is. Best with dense
              retrieval; with BM25 its invented numbers can add noise.

Costs: one Haiku call per question, roughly 700 input and 250 output tokens, about $0.0002 at
Claude Haiku 5.5 prices, plus 300-1500 ms of latency BEFORE retrieval can start. The searches
themselves multiply (one per query), so measure both. Rewrites are cached per question.

Offline: replay_rewriter(fixtures) answers from a JSONL file of rewrites through the real
llmkit request path (ragkit.replay). The lab ships hand-written fixtures (labeled as such) and
--record writes real ones from a live model.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

from pydantic import BaseModel, Field

from llmkit import LLM
from llmkit.structured import StructuredError, complete_structured

from .hybrid import fuse_hits
from .metrics import is_hebrew
from .replay import body_text, replay_llm
from .retrieval.base import Retriever, Where
from .types import Hit

MARKER = "ACME QUERY REWRITER"
MODES = ("multi", "decompose", "translate", "stepback", "hyde")


class QueryRewrite(BaseModel):
    """What the model returns. Field order matters: the model writes top to bottom."""
    language: str = Field(description='Language of the question: "en" or "he".')
    translation: Optional[str] = Field(
        default=None, description="The question translated into the OTHER language (English <-> Hebrew). "
        "Keep product names, codes, numbers and identifiers exactly as written.")
    variants: list[str] = Field(
        default_factory=list, description="2-3 rephrasings of the whole question with different words a "
        "document might use (synonyms, formal policy wording). Same language as the question.")
    subquestions: list[str] = Field(
        default_factory=list, description="Only if answering needs facts from more than one document: 2-3 "
        "self-contained sub-questions to look up separately, in order. Otherwise an empty list.")
    step_back: Optional[str] = Field(
        default=None, description="A more general question about the topic the answer belongs to.")
    hypothetical_answer: Optional[str] = Field(
        default=None, description="One or two sentences that a company document could contain and that "
        "would answer the question. Invented details are fine: this text is only used for search.")


SYSTEM = f"""{MARKER}
You rewrite search queries for the internal knowledge base of Acme Ltd., a 120-person SaaS
company (HR policies, IT and security policies, runbooks, postmortems, price lists, meeting
notes). Most documents are in English; some are in Hebrew. A search engine (BM25 keyword
search plus an embedding index) will run every query you return; the results are fused.

Rules:
- Do not answer the question from your own knowledge. You only write queries.
- Keep identifiers, product and team names, numbers, dates and codes exactly as written.
- Sub-questions must be understandable on their own (no "it" or "that service").
- Leave subquestions empty for a question that one document can answer."""


def build_prompt(question: str) -> str:
    return f"Question: {question}"


@dataclass
class RewriteResult:
    question: str
    value: QueryRewrite
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    cached: bool = False
    error: Optional[str] = None


def queries_for(question: str, rw: QueryRewrite, modes: Sequence[str]) -> list[tuple[str, str]]:
    """[(label, query)] to search: the original first, then one entry per requested rewrite."""
    out = [("original", question)]
    for m in modes:
        if m == "multi":
            out += [(f"variant{i}", v) for i, v in enumerate(rw.variants[:3], 1)]
        elif m == "decompose":
            out += [(f"sub{i}", s) for i, s in enumerate(rw.subquestions[:3], 1)]
        elif m == "translate" and rw.translation:
            out.append(("translation", rw.translation))
        elif m == "stepback" and rw.step_back:
            out.append(("step_back", rw.step_back))
        elif m == "hyde" and rw.hypothetical_answer:
            out.append(("hyde", rw.hypothetical_answer))
        elif m not in MODES:
            raise ValueError(f"unknown mode {m!r}; choose from {MODES}")
    seen, uniq = set(), []
    for label, q in out:
        key = q.strip().lower()
        if key and key not in seen:
            seen.add(key)
            uniq.append((label, q))
    return uniq


def empty_rewrite(question: str) -> QueryRewrite:
    return QueryRewrite(language="he" if is_hebrew(question) else "en")


class QueryRewriter:
    """One structured call per question, cached in memory; optional JSONL recording."""

    def __init__(self, llm: LLM, *, max_tokens: int = 700, record_path: Optional[Union[str, Path]] = None,
                 fail_open: bool = True):
        self.llm = llm
        self.max_tokens = max_tokens
        self.record_path = Path(record_path) if record_path else None
        self.fail_open = fail_open           # on a model error: search with the original only
        self.cache: dict[str, RewriteResult] = {}
        self.calls = 0
        self.total_cost = 0.0

    def rewrite(self, question: str) -> RewriteResult:
        if question in self.cache:
            # Served from memory: free now, but report what the call cost (and took) when it
            # was made, so a pipeline report shows the price of the stage, not of the cache.
            r = self.cache[question]
            return RewriteResult(r.question, r.value, r.input_tokens, r.output_tokens, r.cost_usd,
                                 r.latency_s, cached=True, error=r.error)
        t0 = time.perf_counter()
        try:
            res = complete_structured(self.llm, build_prompt(question), QueryRewrite, system=SYSTEM,
                                      max_tokens=self.max_tokens, max_repairs=1)
            out = RewriteResult(question, res.value, res.input_tokens, res.output_tokens, res.cost_usd,
                                time.perf_counter() - t0)
        except StructuredError as exc:
            if not self.fail_open:
                raise
            r = exc.result
            out = RewriteResult(question, empty_rewrite(question), getattr(r, "input_tokens", 0),
                                getattr(r, "output_tokens", 0), getattr(r, "cost_usd", 0.0),
                                time.perf_counter() - t0, error=str(exc))
        self.calls += 1
        self.total_cost += out.cost_usd
        self.cache[question] = out
        if self.record_path and out.error is None:
            self.record_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.record_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"question": question, "rewrite": out.value.model_dump(),
                                    "model": self.llm.model, "input_tokens": out.input_tokens,
                                    "output_tokens": out.output_tokens, "cost_usd": out.cost_usd,
                                    "latency_s": round(out.latency_s, 3)}, ensure_ascii=False) + "\n")
        return out


class RewritingRetriever:
    """Rewrite the question, search every query with `base`, fuse all lists with RRF.

    orig_weight > 1 keeps the user's own wording dominant (rewrites can drift).
    translation_filter=True searches the translated query only among chunks in the TARGET
    language (where={"language": ...}): a Hebrew query cannot usefully match English chunks
    anyway, and without the filter its matches crowd out the original's."""

    def __init__(self, base: Retriever, rewriter: QueryRewriter, *, modes: Sequence[str] = ("multi", "decompose", "translate"),
                 fetch_k: int = 30, k_rrf: float = 60.0, orig_weight: float = 1.0,
                 translation_filter: bool = True, name: Optional[str] = None):
        bad = [m for m in modes if m not in MODES]
        if bad:
            raise ValueError(f"unknown modes {bad}; choose from {MODES}")
        self.base, self.rewriter, self.modes = base, rewriter, tuple(modes)
        self.fetch_k, self.k_rrf, self.orig_weight = fetch_k, k_rrf, orig_weight
        self.translation_filter = translation_filter
        self.name = name or f"{getattr(base, 'name', 'base')}+rewrite:{','.join(self.modes)}"
        self.last_timing: dict[str, float] = {}
        self.last_queries: list[tuple[str, str]] = []
        self.last_cost = 0.0

    def _where(self, label: str, rw: QueryRewrite, where: Where) -> Where:
        if label != "translation" or not self.translation_filter:
            return where
        target = "en" if rw.language == "he" else "he"
        if where is None:
            return {"language": target}
        if callable(where):
            return lambda c, w=where: w(c) and c.language == target
        return {**where, "language": target}

    def search(self, query: str, k: int = 5, where: Where = None) -> list[Hit]:
        if not self.modes:                       # nothing to rewrite: no LLM call, no cost
            self.last_queries, self.last_cost, self.last_timing = [("original", query)], 0.0, {}
            return self.base.search(query, k=k, where=where)
        t0 = time.perf_counter()
        rr = self.rewriter.rewrite(query)
        t_rw = rr.latency_s * 1000 if rr.cached else (time.perf_counter() - t0) * 1000
        qs = queries_for(query, rr.value, self.modes)
        self.last_queries, self.last_cost = qs, rr.cost_usd
        t1 = time.perf_counter()
        lists = {label: self.base.search(q, k=self.fetch_k,
                                         where=self._where(label, rr.value, where)) for label, q in qs}
        t_search = (time.perf_counter() - t1) * 1000
        weights = [self.orig_weight if label == "original" else 1.0 for label, _ in qs]
        out = fuse_hits(lists, method="rrf", k_rrf=self.k_rrf, weights=weights, name=self.name)
        self.last_timing = {"rewrite_llm": t_rw, "searches": t_search, "n_queries": float(len(qs)),
                            "rewrite_cached": float(rr.cached)}
        return out[:k]


# ---------------------------------------------------------------- offline fixtures
def load_rewrite_fixtures(path: Union[str, Path]) -> dict[str, dict]:
    """JSONL rows {"question", "rewrite": {...QueryRewrite fields}} -> {question: rewrite dict}.
    Later rows win, so appending a recorded run overrides hand-written rows."""
    out: dict[str, dict] = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out[d["question"].strip()] = d["rewrite"]
    return out


_Q = re.compile(r"Question:\s*(.+)", re.S)


def fixture_responder(fixtures: dict[str, dict]):
    """Responder for ragkit.replay: the recorded rewrite of the question, or an empty one."""
    def respond(body: dict) -> str:
        _, user = body_text(body)
        m = _Q.search(user)
        q = m.group(1).strip() if m else ""
        rw = fixtures.get(q)
        if rw is None:
            return empty_rewrite(q).model_dump_json()
        return QueryRewrite.model_validate(rw).model_dump_json()
    return respond


def replay_rewriter(fixtures: Union[str, Path, dict], model: str = "claude-haiku-5-5") -> QueryRewriter:
    fx = fixtures if isinstance(fixtures, dict) else load_rewrite_fixtures(fixtures)
    return QueryRewriter(replay_llm(fixture_responder(fx), model))


__all__ = ["QueryRewrite", "QueryRewriter", "RewriteResult", "RewritingRetriever", "queries_for", "MODES",
           "SYSTEM", "MARKER", "build_prompt", "load_rewrite_fixtures", "fixture_responder", "replay_rewriter",
           "empty_rewrite"]
