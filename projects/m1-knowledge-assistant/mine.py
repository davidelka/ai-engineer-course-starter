"""Your code for midterm project M1, the Acme Knowledge Assistant.

You build the parts of the assistant that the lessons of phase 2 taught; the course gives you the
rest ready (ingestion, the HTTP service and UI, the command line, the data path's SQL engine).
Six functions, in five milestones:

    M3  build_retriever     the retriever stack: hybrid, version filter, optional reranker
    M4  pack_context        from 30 ranked candidates to the chunks the model reads
    M5  build_request       the prompt: cached system block + numbered sources + question
    M5  resolve_citations   from "[2]" in the answer to a passage the user can open
    M6  route_question      documents or database?
    M8  answer_metrics      the per-question numbers of the evaluation

Each is checked by tests in ./tests (python -m pytest -q tests/test_m3_retriever.py, ...). Every
command of the project (`python -m acmeqa ...`, the service, the evaluation) calls YOUR functions;
a command that needs a function you have not written yet stops and names the milestone.
The reference implementations are on the repo's `solutions` branch, for comparing AFTER your
tests pass. Stuck? HINTS.md has three graded hints per function.

The types you work with (ragkit/types.py):
    Hit    .chunk (a Chunk), .score (float), .rank (1-based), .scores (dict of every stage's score)
    Chunk  .id ("<doc_id>#<index>"), .doc_id, .text, .start, .end (char offsets into the cleaned
           document text: doc.text[start:end] == text), .section (str, "A > B"), .title,
           .effective_date ("YYYY-MM-DD" or ""), .version (str or ""), .meta (dict)
"""

from __future__ import annotations

import re  # noqa: F401  (you will likely need it)
from dataclasses import replace  # noqa: F401
from typing import Any, Callable, Optional, Sequence

from html import escape  # noqa: F401
from xml.sax.saxutils import quoteattr  # noqa: F401

from acmeqa.answer import SYSTEM  # noqa: F401
from acmeqa.citations import CITE_RE, Citation, snippet_of  # noqa: F401
from acmeqa.router import AGG_CUES, DOC_CUES, ENTITY_CUES, Route  # noqa: F401
from llmkit import ChatRequest, Message  # noqa: F401
from llmkit.types import Block  # noqa: F401
from ragkit.clean import collapse_ws, normalize  # noqa: F401
from ragkit.rerank import RerankingRetriever, make_reranker  # noqa: F401
from ragkit.tokens import get_tokenizer  # noqa: F401
from ragkit.types import Hit
from ragkit.versions import VersionAwareRetriever, supersedes_map  # noqa: F401


# ------------------------------------------------------------------ M3: the retriever stack
def build_retriever(job, s=None, *, upto: str = "full") -> Any:
    """Return the retriever the assistant searches with. Every layer has search(query, k, where).

    `job` is the IngestJob (acmeqa/ingest.py). It already holds the first-stage retrievers:
    job.bm25 (BM25Index), job.dense (dense retriever), job.index (the two fused with RRF), and
    job.all_chunks(). `s` is the Settings (defaults to job.s): s.version_mode is "off",
    "retrieved" or "corpus", and s.rerank is None or a reranker spec such as "fake" or "ce:bge-m3".

    `upto` stops the stack at a layer, for the ablation in the evaluation:
    - "bm25" -> job.bm25;  "dense" -> job.dense;  "hybrid" -> job.index;
    - "versions" -> the hybrid wrapped by the version filter, or the hybrid itself when
      version_mode == "off";
    - "full" -> "versions", wrapped by a reranker when s.rerank is set.
    The version filter is ragkit's VersionAwareRetriever with fetch_k=50 (in "corpus" mode it needs
    superseded_by=supersedes_map(job.all_chunks())). The reranker is RerankingRetriever with
    make_reranker(s.rerank) and fetch_k=30.

    Stuck? HINTS.md -> build_retriever
    """
    # TODO(M3)
    raise NotImplementedError("M3: implement build_retriever")


# ------------------------------------------------------------------ M4: context packing
def pack_context(hits: Sequence[Hit], *, max_chunks: int = 6, max_tokens: int = 1800, max_per_doc: int = 2,
                 count: Optional[Callable[[str], int]] = None) -> list[Hit]:
    """Choose the chunks for the prompt from `hits` (ranked, best first).

    Returns NEW Hits (the input hits are not modified), in input order, with rank renumbered
    1..n and a copy of `scores`. Empty input -> [].
    The result must satisfy:
    - at most `max_chunks` hits;
    - no two kept hits with the same text after collapse_ws(normalize(text)).lower()
      (it-laptop-policy and it-laptop-faq repeat whole paragraphs);
    - at most `max_per_doc` hits per doc_id;
    - the total count(chunk.text) of the kept hits is <= `max_tokens`. A hit that does not fit is
      skipped, not a reason to stop: a smaller hit further down may still fit. Exception: the
      first kept hit is always kept, even when it alone is over the budget.
    count defaults to get_tokenizer("approx").count.

    Stuck? HINTS.md -> pack_context
    """
    # TODO(M4)
    raise NotImplementedError("M4: implement pack_context")


# ------------------------------------------------------------------ M5: the request
def build_request(question: str, context: Sequence[Hit], *, max_tokens: int = 500, cache: bool = True) -> ChatRequest:
    """Build the ChatRequest that asks the model to answer `question` from `context` (the packed hits).

    - system: SYSTEM (acmeqa/answer.py, the rules and two examples) as [Block(SYSTEM, cache="5m")]
      when cache is True, else the plain string. It must be identical for every question: it is
      the prefix that prompt caching keys on.
    - one user message, exactly:
          "<sources>\n" + <the sources joined by "\n"> + "\n</sources>\n\n<question>" + q + "</question>"
      where q is the question with & < > escaped (html.escape(question, quote=False)), and an empty
      context is the text "(no sources found)" in place of the sources.
    - source n (1-based, in context order) is:
          '<source id="n" doc=... title=... section=... effective_date=... version=...>\n'
          + <the chunk text with & < > escaped> + "\n</source>"
      Attributes in that order, each value quoted with xml.sax.saxutils.quoteattr, and an attribute
      whose value is empty is left out (id is always there).
    - max_tokens as given.
    The exact format matters: recorded answers are replayed by the exact prompt, and the offline
    answerer reads the sources back from it. Escaping is a defence too: a document that contains
    "</source>" must not be able to close the tag and talk to the model as an instruction.

    Stuck? HINTS.md -> build_request
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement build_request")


# ------------------------------------------------------------------ M5: citations
def resolve_citations(text: str, context: Sequence[Hit]) -> list[Citation]:
    """Turn the [n] markers of an answer into Citations, checked against the context that was sent.

    - Markers: "[2]", grouped "[1, 3]" or "[1;3]"; "[1][3]" is two markers. No markers -> [].
    - One Citation per distinct number, in order of first appearance.
    - Valid (1 <= n <= len(context)): every field comes from context[n-1].chunk:
        Citation(n, True, doc_id, chunk_id=chunk.id, title=chunk.title, section=chunk.section or None,
                 effective_date=chunk.effective_date or None, start=chunk.start, end=chunk.end,
                 snippet=snippet_of(chunk.text))
    - Invalid (0, or more than the number of sources): Citation(n=n, valid=False), other fields
      None. The model invented a source; the UI shows it in red and the evaluation counts it.

    Stuck? HINTS.md -> resolve_citations
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement resolve_citations")


# ------------------------------------------------------------------ M6: the router
def route_question(question: str) -> Route:
    """Decide the path of a question: Route(kind, reason, matched).

    The cues are the regexes in DOC_CUES, AGG_CUES and ENTITY_CUES (acmeqa/router.py); matching
    ignores case and extra whitespace. `matched` holds the matched TEXT of each cue that fired, in list order.
    - any doc cue fires          -> Route("docs", "policy/process wording", <the doc matches>)
    - an aggregate AND an entity cue fire (no doc cue)
                                 -> Route("data", "aggregate over a table entity", <agg> + <entity>)
    - otherwise                  -> Route("docs", "no aggregate + table entity", <agg> + <entity>)

    Examples: "How many open P1 tickets do we have right now?" -> data, matched ["how many", "tickets", "p1"];
    "How many sick days do employees in Israel accrue per year?" -> docs (doc cue "accrue");
    "כמה קריאות P1 פתוחות יש כרגע?" -> data; "What is a Red Folder account?" -> docs.

    Stuck? HINTS.md -> route_question
    """
    # TODO(M6)
    raise NotImplementedError("M6: implement route_question")


# ------------------------------------------------------------------ M8: the answer metrics
def answer_metrics(q: dict, context_docs: Sequence[str], cited: Sequence[str], refused: bool) -> dict:
    """The numbers the evaluation keeps for one golden question.

    `q` is a golden question (data/acme/corpus/golden/qa.jsonl): q["source_ids"] lists the documents
    that hold the answer (empty for a question the corpus cannot answer), and q["tags"] may hold
    "stale:<doc_id>" for each superseded version of a source. `context_docs` are the doc ids that
    were in the prompt, `cited` the doc ids the answer cited, `refused` whether it said
    "not in the documents". Duplicates in the lists count once.

    Returns a dict with exactly these keys:
    - "context_recall": the share of source_ids that reached the prompt;
    - "citation_precision": the share of cited docs that are sources (0.0 when nothing is cited);
    - "citation_recall": the share of source_ids that were cited;
    - "stale_cited": True when a cited doc is one of the stale ids;
    - "abstain_ok": did the assistant do the right thing about refusing (answer when the corpus
      has the answer, refuse when it does not).
    For an unanswerable question (no source_ids) the three shares are None.

    Stuck? HINTS.md -> answer_metrics
    """
    # TODO(M8)
    raise NotImplementedError("M8: implement answer_metrics")
