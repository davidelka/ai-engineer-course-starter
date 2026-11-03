"""Measurements for this lesson. Lesson 13 adds the full RAG evaluation (faithfulness,
answer correctness with an LLM judge, context precision); these are the cheap, exact ones.

- quote_coverage: for every golden source quote, is it fully inside ONE chunk? It separates
  two different failures: "missing" (the quote is not in the extracted document at all: an
  extraction/cleaning failure) and "split" (it is in the document but every chunk cuts it:
  a chunking failure). Neither is visible in an answer; both make the answer impossible.
- retrieval_eval: for every golden question, did the top-k contain a chunk of a source
  document (doc hit) and a chunk that contains a golden quote (quote hit)?
- answer_checks: citation and abstention checks on generated answers.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .clean import collapse_ws
from .retrieval.base import Retriever
from .types import Chunk, Document


def norm(s: str) -> str:
    """The comparison form: normalize() + collapse whitespace. Markdown table pipes and list
    markers added by loaders are not removed, so a quote that spans two table cells will not
    match: that is a real limitation of quote-based checks, and the golden set avoids it."""
    return collapse_ws(s)


def quote_status(quote: str, doc_text: str, chunk_texts: Iterable[str]) -> str:
    """"covered" if the quote (whitespace-normalized) is inside one chunk, "split" if it is in
    the document but in no single chunk, "missing" if it is not in the document at all."""
    q = norm(quote)
    if q not in norm(doc_text):
        return "missing"
    return "covered" if any(q in norm(t) for t in chunk_texts) else "split"


@dataclass
class QuoteRow:
    qid: str
    qtype: str
    source_id: str
    quote: str
    status: str                       # "covered" | "split" | "missing" | "no_doc"
    chunk_id: Optional[str] = None


@dataclass
class CoverageReport:
    rows: list[QuoteRow] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(1 for r in self.rows if r.status == status)

    @property
    def coverage(self) -> float:
        return self.count("covered") / max(1, len(self.rows))

    def summary(self) -> str:
        n = len(self.rows)
        return (f"{self.count('covered')}/{n} covered ({self.coverage:.1%}), "
                f"split {self.count('split')}, missing {self.count('missing')}, "
                f"no_doc {self.count('no_doc')}")


def quote_coverage(docs: Iterable[Document], chunks: Iterable[Chunk], qa: list[dict]) -> CoverageReport:
    doc_text = {d.id: norm(d.text) for d in docs}
    by_doc: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for c in chunks:
        by_doc[c.doc_id].append((c.id, norm(c.text)))
    rep = CoverageReport()
    for q in qa:
        for sq in q.get("source_quotes", []):
            sid, quote = sq["source_id"], norm(sq["quote"])
            if sid not in doc_text:
                status, cid = "no_doc", None
            elif quote not in doc_text[sid]:
                status, cid = "missing", None
            else:
                cid = next((i for i, t in by_doc.get(sid, []) if quote in t), None)
                status = "covered" if cid else "split"
            rep.rows.append(QuoteRow(q["id"], q.get("type", ""), sid, sq["quote"], status, cid))
    return rep


@dataclass
class RetrievalRow:
    qid: str
    qtype: str
    question: str
    doc_hit: bool
    quote_hit: bool
    first_rank: Optional[int]          # rank of the first chunk from a source doc
    retrieved_docs: list[str]
    all_docs_hit: bool = False         # every source doc is in the top-k (what multi-hop needs)


def retrieval_eval(retriever: Retriever, qa: list[dict], k: int = 5, *,
                   answerable_only: bool = True) -> list[RetrievalRow]:
    rows = []
    for q in qa:
        if answerable_only and not q.get("source_ids"):
            continue
        hits = retriever.search(q["question"], k=k)
        srcs = set(q.get("source_ids", []))
        quotes = [(sq["source_id"], norm(sq["quote"])) for sq in q.get("source_quotes", [])]
        first = next((h.rank for h in hits if h.chunk.doc_id in srcs), None)
        quote_hit = any(h.chunk.doc_id == sid and qt in norm(h.chunk.text)
                        for h in hits for sid, qt in quotes)
        got = [h.chunk.doc_id for h in hits]
        rows.append(RetrievalRow(q["id"], q.get("type", ""), q["question"], first is not None,
                                 quote_hit, first, got, all_docs_hit=srcs <= set(got)))
    return rows


def rate_by_type(rows: list, attr: str) -> dict[str, tuple[int, int]]:
    """{type: (passed, total)} plus "ALL"."""
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        for key in (r.qtype, "ALL"):
            out[key][0] += int(bool(getattr(r, attr)))
            out[key][1] += 1
    return {k: (v[0], v[1]) for k, v in sorted(out.items(), key=lambda kv: (kv[0] == "ALL", kv[0]))}


STALE_RE = re.compile(r"^stale:(.+)$")


def answer_checks(q: dict, ans) -> dict:
    """Cheap checks on one RagAnswer against its golden question:
    - abstain_ok: unanswerable -> abstained; answerable -> did not abstain
    - cited_source: at least one cited chunk comes from a golden source document
    - cited_all_sources: every golden source document is cited (multi-hop needs this)
    - cited_stale: a cited chunk comes from the superseded version (tag stale:<id>)
    - invalid_citations: [n] that point to nothing."""
    unanswerable = not q.get("source_ids")
    stale = {m.group(1) for t in q.get("tags", []) or [] for m in [STALE_RE.match(t)] if m}
    cited = set(ans.cited_doc_ids)
    return {
        "abstain_ok": ans.abstained if unanswerable else not ans.abstained,
        "cited_source": (not unanswerable) and bool(cited & set(q.get("source_ids", []))),
        "cited_all_sources": (not unanswerable) and set(q.get("source_ids", [])) <= cited,
        "cited_stale": bool(cited & stale),
        "invalid_citations": len(ans.invalid_citations),
    }
