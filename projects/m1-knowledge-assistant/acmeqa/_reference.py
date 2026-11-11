"""Reference implementations of the M1 milestones (solutions branch only).

This file exists only on the `solutions` branch of the course repo. On `main` the project runs
your functions from mine.py, and a milestone you have not written yet stops the command with a
message that names it. Compare with this file AFTER your tests pass.
"""

from __future__ import annotations

import re
from dataclasses import replace
from html import escape
from typing import Any, Callable, Optional, Sequence, Union
from xml.sax.saxutils import quoteattr

from llmkit import ChatRequest, Message
from llmkit.types import Block
from ragkit.clean import collapse_ws, normalize
from ragkit.tokens import get_tokenizer
from ragkit.types import Hit
from ragkit.versions import VersionAwareRetriever, supersedes_map

from .answer import SYSTEM
from .citations import CITE_RE, Citation, snippet_of
from .router import AGG_CUES, DOC_CUES, ENTITY_CUES, Route


# ------------------------------------------------------------------ M3: the retriever stack
def build_retriever(job, s=None, *, upto: str = "full") -> Any:
    s = s or job.s
    if upto == "bm25":
        return job.bm25
    if upto == "dense":
        return job.dense
    r: Any = job.index
    if upto == "hybrid":
        return r
    if s.version_mode != "off":
        sup = supersedes_map(job.all_chunks()) if s.version_mode == "corpus" else None
        r = VersionAwareRetriever(r, mode=s.version_mode, superseded_by=sup, fetch_k=50)
    if upto == "versions":
        return r
    if s.rerank:
        from ragkit.rerank import RerankingRetriever, make_reranker
        r = RerankingRetriever(r, make_reranker(s.rerank), fetch_k=30)
    return r


# ------------------------------------------------------------------ M4: context packing
def _key(text: str) -> str:
    return collapse_ws(normalize(text)).lower()


def pack_context(hits: Sequence[Hit], *, max_chunks: int = 6, max_tokens: int = 1800, max_per_doc: int = 2,
                 count: Optional[Callable[[str], int]] = None) -> list[Hit]:
    count = count or get_tokenizer("approx").count
    chosen: list[Hit] = []
    seen: set[str] = set()
    per_doc: dict[str, int] = {}
    used = 0
    for h in hits:
        if len(chosen) >= max_chunks:
            break
        key = _key(h.chunk.text)
        if key in seen:
            continue
        if per_doc.get(h.chunk.doc_id, 0) >= max_per_doc:
            continue
        n = count(h.chunk.text)
        if chosen and used + n > max_tokens:
            continue
        chosen.append(h)
        seen.add(key)
        per_doc[h.chunk.doc_id] = per_doc.get(h.chunk.doc_id, 0) + 1
        used += n
    return [replace(h, rank=i, scores=dict(h.scores)) for i, h in enumerate(chosen, start=1)]


# ------------------------------------------------------------------ M5: the request and the citations
def format_source(n: int, hit: Hit) -> str:
    c = hit.chunk
    attrs = {"id": str(n), "doc": c.doc_id, "title": c.title, "section": c.section,
             "effective_date": c.effective_date, "version": c.version}
    a = " ".join(f"{k}={quoteattr(v)}" for k, v in attrs.items() if v)
    return f"<source {a}>\n{escape(c.text, quote=False)}\n</source>"


def build_request(question: str, context: Sequence[Hit], *, max_tokens: int = 500, cache: bool = True) -> ChatRequest:
    sources = "\n".join(format_source(i + 1, h) for i, h in enumerate(context)) or "(no sources found)"
    user = f"<sources>\n{sources}\n</sources>\n\n<question>{escape(question, quote=False)}</question>"
    system: Union[str, list] = [Block(SYSTEM, cache="5m")] if cache else SYSTEM
    return ChatRequest(messages=[Message("user", user)], system=system, max_tokens=max_tokens)


def resolve_citations(text: str, context: Sequence[Hit]) -> list[Citation]:
    out: list[Citation] = []
    seen: set[int] = set()
    for m in CITE_RE.finditer(text):
        for part in re.split(r"[,;]", m.group(1)):
            n = int(part.strip())
            if n in seen:
                continue
            seen.add(n)
            if 1 <= n <= len(context):
                c = context[n - 1].chunk
                out.append(Citation(n=n, valid=True, doc_id=c.doc_id, chunk_id=c.id, title=c.title,
                                    section=c.section or None, effective_date=c.effective_date or None,
                                    start=c.start, end=c.end, snippet=snippet_of(c.text)))
            else:
                out.append(Citation(n=n, valid=False))
    return out


# ------------------------------------------------------------------ M6: the router
def _found(patterns: list[str], text: str) -> list[str]:
    out = []
    for p in patterns:
        m = re.search(p, text)
        if m:
            out.append(m.group(0))
    return out


def route_question(question: str) -> Route:
    q = " ".join(question.lower().split())
    doc = _found(DOC_CUES, q)
    if doc:
        return Route("docs", "policy/process wording", doc)
    agg, ent = _found(AGG_CUES, q), _found(ENTITY_CUES, q)
    if agg and ent:
        return Route("data", "aggregate over a table entity", agg + ent)
    return Route("docs", "no aggregate + table entity", agg + ent)


# ------------------------------------------------------------------ M8: the answer metrics
def answer_metrics(q: dict, context_docs: Sequence[str], cited: Sequence[str], refused: bool) -> dict:
    srcs = set(q.get("source_ids") or [])
    stale = {t.split(":", 1)[1] for t in (q.get("tags") or []) if t.startswith("stale:")}
    ctx, cit = set(context_docs), set(cited)
    if srcs:
        inter = len(cit & srcs)
        precision: Optional[float] = inter / len(cit) if cit else 0.0
        recall: Optional[float] = inter / len(srcs)
        context_recall: Optional[float] = len(srcs & ctx) / len(srcs)
        abstain_ok = not refused
    else:
        precision = recall = context_recall = None
        abstain_ok = refused
    return {"context_recall": context_recall, "citation_precision": precision, "citation_recall": recall,
            "stale_cited": bool(cit & stale), "abstain_ok": abstain_ok}
