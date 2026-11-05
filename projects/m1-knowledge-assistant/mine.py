"""Your code for midterm project M1 (the Acme Knowledge Assistant). Three milestones are coding TODOs:

    M4  pack_context        from 30 ranked candidates to the chunks the model reads
    M5  resolve_citations   from "[2]" in the answer to a passage the user can open
    M6  route_question      documents or database?

Each is checked by tests in ./tests (python -m pytest -q tests). Every command of the project
(`python -m acmeqa ...`, the service, the evaluation) uses YOUR function as soon as it stops
raising NotImplementedError, and the reference until then (it says so once per run on stderr).
`--reference` forces the references. They are in acmeqa/context.py, acmeqa/citations.py and
acmeqa/router.py: try not to read them before your tests pass.

The types you work with (ragkit/types.py):
    Hit    .chunk (a Chunk), .score (float), .rank (1-based), .scores (dict of every stage's score)
    Chunk  .id ("<doc_id>#<index>"), .doc_id, .text, .start, .end (char offsets into the cleaned
           document text: doc.text[start:end] == text), .section (str, "A > B"), .title,
           .effective_date ("YYYY-MM-DD" or ""), .meta (dict)
"""

from __future__ import annotations

import re  # noqa: F401  (you will likely need it)
from dataclasses import replace  # noqa: F401
from typing import Callable, Optional, Sequence

from acmeqa.citations import CITE_RE, Citation, snippet_of  # noqa: F401
from acmeqa.router import AGG_CUES, DOC_CUES, ENTITY_CUES, Route  # noqa: F401
from ragkit.clean import collapse_ws, normalize  # noqa: F401
from ragkit.tokens import get_tokenizer  # noqa: F401
from ragkit.types import Hit


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
