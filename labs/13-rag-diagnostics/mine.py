"""Your code for lesson 13. Each part is checked by tests in ./tests.

Reference versions exist in ragkit/diagnose.py (classify, context_recall, context_precision,
citation_precision, citation_recall, check_claims). Try not to peek before your tests pass.

    python -m pytest -q labs/13-rag-diagnostics/tests

Exercise 5 is not code: fill TRACE_GUESSES at the bottom after reading the six traces.

Each docstring is a contract: what goes in, what comes out, and the rules the result must follow.
When you are stuck, HINTS.md has graded hints for every function (direction, structure, full algorithm).
"""

from __future__ import annotations

from typing import Any, Collection, Optional, Sequence

from ragkit.diagnose import (Case, ClaimResult, Claims, ClaimVerdicts, DECOMPOSE_SYSTEM,  # noqa: F401
                             GroundednessReport, VERIFY_SYSTEM, decompose_prompt, evidence_in_context,
                             verify_prompt)


# ------------------------------------------------------------------ exercise 1
def classify_failure(case: Case, min_facts: float = 0.5, long_context: int = 4000) -> str:
    """Return the ROOT-CAUSE stage of one question: "ok" or one of ragkit.diagnose.STAGES.

    `case` is a ragkit.diagnose.Case (read its docstring for every field).

    - Unanswerable question (source_ids == []): "ok" if it abstained, else "failed_to_refuse".
    - An answerable question PASSES ("ok") unless at least one of these holds: it abstained;
      fact_coverage < min_facts; a cited doc is stale; grounded is False; it answered but cited
      no doc from source_ids; invalid_citations > 0. None (not measured) is never a failure.
    - A failed question gets the FIRST stage that fails when you walk the pipeline: ingestion
      (quote_status), then retrieval, then generation (the comments on STAGES say what each
      stage means). Later problems are symptoms, not the root cause. In generation, an answer
      with grounded False is a "hallucination" before it is lost_in_middle or ignored_context,
      and "wrong_citation" is what remains when nothing else explains the failure.
    - "lost_in_middle" needs a long context (context_tokens >= long_context), at least 3 chunks,
      and evidence that is never at the first or the last prompt position.

        Case(source_ids=["a"], quote_status=["covered"], candidates=["a", "b"], context=["b"],
             cited=["b"], fact_coverage=0.0)                       -> "ranked_low"
        Case(source_ids=[], abstained=False)                       -> "failed_to_refuse"

    Stuck? HINTS.md -> classify_failure
    """
    raise NotImplementedError("exercise 1: classify_failure")


# ------------------------------------------------------------------ exercise 2
def context_recall(quotes: Sequence[str], context_texts: Sequence[str]) -> Optional[float]:
    """Share of golden evidence quotes found WHOLE in at least one context chunk.

    Matching ignores case and runs of whitespace (ragkit.clean.collapse_ws is relevant). A quote
    counts once even if several chunks contain it. None if quotes is empty.

        context_recall(["Up to 5 days.", "Expire  on March 31."],
                       ["... up to 5 days. Carried ...", "nothing"])   -> 0.5

    Stuck? HINTS.md -> context_recall
    """
    raise NotImplementedError("exercise 2: context_recall")


def context_precision(relevance: Sequence[bool]) -> Optional[float]:
    """Rank-aware context precision, the Ragas definition: relevant chunks near the top of the
    prompt score higher than the same chunks lower down. relevance[i] says whether the chunk at
    prompt position i+1 is relevant.

    None for an empty list; 0.0 when nothing is relevant; 1.0 when every relevant chunk comes
    before every irrelevant one.
        [True, False, True]   -> 0.8333
        [False, True]         -> 0.5

    Stuck? HINTS.md -> context_precision
    """
    raise NotImplementedError("exercise 2: context_precision")


def citation_precision(cited: Sequence[int], supporting: Collection[int]) -> Optional[float]:
    """Share of DISTINCT cited source numbers (the n of [n]) that are in `supporting` (the prompt
    positions whose chunk contains golden evidence). A number that points to no source (an
    invented [9]) is simply not supporting. Duplicates count once. None if nothing is cited.

        citation_precision([1, 3, 1], {1, 2})   -> 0.5

    Stuck? HINTS.md -> citation_precision
    """
    raise NotImplementedError("exercise 2: citation_precision")


def citation_recall(cited: Sequence[int], quote_locs: Sequence[Collection[int]]) -> Optional[float]:
    """quote_locs[i] = the prompt positions that contain golden quote i (empty if the quote never
    reached the prompt). Return the share of quotes for which at least one of their positions was
    cited. A quote with no position counts as missed. None if quote_locs is empty.

        citation_recall([1], [{1}, {2, 3}])   -> 0.5
        citation_recall([2], [{1}, set()])    -> 0.0

    Stuck? HINTS.md -> citation_recall
    """
    raise NotImplementedError("exercise 2: citation_recall")


# ------------------------------------------------------------------ exercise 3
def check_claims(answer: str, contexts: Sequence[Any], llm: Any, max_tokens: int = 1200) -> GroundednessReport:
    """Claim-level groundedness: split the answer into claims, then have a judge verify each one
    against the contexts. Two structured calls (llmkit.structured.complete_structured), using
    the imported Claims / ClaimVerdicts models, decompose_prompt / verify_prompt and
    DECOMPOSE_SYSTEM / VERIFY_SYSTEM, each with max_tokens=max_tokens.

    contexts: the chunk texts that were in the prompt (strings), source 1 first.

    Returns a GroundednessReport (its .score, .label and .unsupported are computed for you):
    - refusal=True and NO LLM call when the answer is empty or says "not in the documents" (any case);
    - one ClaimResult per non-empty (stripped) claim, in order; no claims -> no verify call;
    - a claim the judge gave no verdict for is "not_found";
    - for a "supported" verdict, evidence_verified says whether the judge's evidence really is in
      the contexts (evidence_in_context); for other verdicts it is None;
    - cost_usd = the total cost of the calls made;
    - a StructuredError is never raised: report.error = f"{exc.stage}: {exc}".

    Stuck? HINTS.md -> check_claims
    """
    raise NotImplementedError("exercise 3: check_claims")


# ------------------------------------------------------------------ exercise 5 (not code)
# Read the six traces (python labs/13-rag-diagnostics/traces.py) and write the root-cause stage
# you would assign to each one: "ok" or one of ragkit.diagnose.STAGES. Then run
# python labs/13-rag-diagnostics/traces.py --check
TRACE_GUESSES: dict[str, str] = {
    "T1": "",
    "T2": "",
    "T3": "",
    "T4": "",
    "T5": "",
    "T6": "",
}
