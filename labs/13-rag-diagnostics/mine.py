"""Your code for lesson 13. Each part is checked by tests in ./tests.

Reference versions exist in ragkit/diagnose.py (classify, context_recall, context_precision,
citation_precision, citation_recall, check_claims). Try not to peek before your tests pass.

    python -m pytest -q labs/13-rag-diagnostics/tests

Exercise 5 is not code: fill TRACE_GUESSES at the bottom after reading the six traces.
"""

from __future__ import annotations

from typing import Any, Collection, Optional, Sequence

from ragkit.diagnose import (Case, ClaimResult, Claims, ClaimVerdicts, DECOMPOSE_SYSTEM,  # noqa: F401
                             GroundednessReport, VERIFY_SYSTEM, decompose_prompt, evidence_in_context,
                             verify_prompt)


# ------------------------------------------------------------------ exercise 1
def classify_failure(case: Case, min_facts: float = 0.5, long_context: int = 4000) -> str:
    """Return the ROOT-CAUSE stage of one question: "ok" or one of ragkit.diagnose.STAGES.

    `case` is a ragkit.diagnose.Case (read its docstring): golden data (source_ids, quote_status,
    stale_ids) plus what the pipeline did (candidates, context, evidence_positions, context_tokens,
    abstained, cited, invalid_citations, fact_coverage, grounded).

    Step A, unanswerable questions (source_ids == []):
        "ok" if case.abstained, else "failed_to_refuse". Nothing else matters.

    Step B, did the answerable question pass? It FAILS if any of these holds:
        - abstained
        - fact_coverage is not None and fact_coverage < min_facts
        - a cited doc is in stale_ids
        - grounded is False                      (None means "not judged": not a failure)
        - not abstained and no cited doc is in source_ids
        - invalid_citations > 0
      If none holds, return "ok".

    Step C, a failed answerable question: walk the pipeline and return the FIRST stage that fails.
        1. "no_doc" in quote_status   -> "missing_from_corpus"
        2. "missing" in quote_status  -> "extraction_lost"
        3. "split" in quote_status    -> "chunk_split"
        4. some source_id not in candidates -> "not_retrieved"
        5. some source_id not in context    -> "ranked_low"
        6. a cited doc is in stale_ids      -> "stale_version"
        7. abstained                        -> "false_refusal"
        8. fact_coverage < min_facts (and not None):
              grounded is False                    -> "hallucination"
              lost in the middle (below)           -> "lost_in_middle"
              otherwise                            -> "ignored_context"
        9. grounded is False                -> "hallucination"
       10. otherwise                        -> "wrong_citation"

    "Lost in the middle" means ALL of: context_tokens >= long_context, len(context) >= 3,
    evidence_positions is not empty, and every position p satisfies 1 < p < len(context)
    (the evidence is never first and never last).

        Case(source_ids=["a"], quote_status=["covered"], candidates=["a", "b"], context=["b"],
             cited=["b"], fact_coverage=0.0)                       -> "ranked_low"
        Case(source_ids=[], abstained=False)                       -> "failed_to_refuse"
    """
    raise NotImplementedError("exercise 1: classify_failure")


# ------------------------------------------------------------------ exercise 2
def context_recall(quotes: Sequence[str], context_texts: Sequence[str]) -> Optional[float]:
    """Share of golden evidence quotes found WHOLE in at least one context chunk.

    Compare after normalizing both sides: collapse whitespace (ragkit.clean.collapse_ws) and
    lowercase. A quote counts once even if several chunks contain it. None if quotes is empty.

        context_recall(["Up to 5 days.", "Expire  on March 31."],
                       ["... up to 5 days. Carried ...", "nothing"])   -> 0.5
    """
    raise NotImplementedError("exercise 2: context_recall")


def context_precision(relevance: Sequence[bool]) -> Optional[float]:
    """Rank-aware context precision (the Ragas definition). relevance[i] says whether the chunk at
    prompt position i+1 is relevant.

        sum over positions k with relevance True of  precision@k
        --------------------------------------------------------   where precision@k =
               number of relevant positions in the list               relevant in top k / k

    None for an empty list; 0.0 when nothing is relevant.
        [True, False, True]   -> (1/1 + 2/3) / 2 = 0.8333
        [False, True]         -> (1/2) / 1      = 0.5
    """
    raise NotImplementedError("exercise 2: context_precision")


def citation_precision(cited: Sequence[int], supporting: Collection[int]) -> Optional[float]:
    """Share of DISTINCT cited source numbers (the n of [n]) that are in `supporting` (the prompt
    positions whose chunk contains golden evidence). A number that points to no source (an
    invented [9]) is simply not in `supporting`. Duplicates count once. None if nothing is cited.

        citation_precision([1, 3, 1], {1, 2})   -> 1/2 = 0.5
    """
    raise NotImplementedError("exercise 2: citation_precision")


def citation_recall(cited: Sequence[int], quote_locs: Sequence[Collection[int]]) -> Optional[float]:
    """quote_locs[i] = the prompt positions that contain golden quote i (empty if the quote never
    reached the prompt). Return the share of quotes for which at least one of their positions was
    cited. A quote with no position counts as missed. None if quote_locs is empty.

        citation_recall([1], [{1}, {2, 3}])   -> 0.5
        citation_recall([2], [{1}, set()])    -> 0.0
    """
    raise NotImplementedError("exercise 2: citation_recall")


# ------------------------------------------------------------------ exercise 3
def check_claims(answer: str, contexts: Sequence[Any], llm: Any, max_tokens: int = 1200) -> GroundednessReport:
    """Claim-level groundedness with two structured calls (llmkit.structured.complete_structured).

    contexts: the chunk texts that were in the prompt (strings), source 1 first.

    1. If the answer is empty or contains "not in the documents" (any case): return
       GroundednessReport(refusal=True) WITHOUT calling the LLM.
    2. Decompose: complete_structured(llm, decompose_prompt(answer), Claims,
       system=DECOMPOSE_SYSTEM, max_tokens=max_tokens). Strip each claim; drop empty ones.
       No claims left -> return the report (with the cost so far).
    3. Verify: complete_structured(llm, verify_prompt(claims, contexts), ClaimVerdicts,
       system=VERIFY_SYSTEM, max_tokens=max_tokens).
    4. Build one ClaimResult per claim, in order, from verdicts[i]:
         - a missing verdict (the judge returned fewer) -> ClaimResult(claim, "not_found")
         - for verdict "supported": evidence_verified = evidence_in_context(v.evidence, contexts, v.source)
           (so a judge that invents its evidence does not get the claim counted as supported)
         - for other verdicts: evidence_verified = None
         ClaimResult(claim=<your claim text>, verdict=v.verdict, evidence=v.evidence,
                     source=v.source, evidence_verified=...)
    5. report.cost_usd = the sum of both calls' .cost_usd.
    6. If complete_structured raises llmkit.structured.StructuredError, return a report with
       error=f"{exc.stage}: {exc}" (and the cost of exc.result if it has one). Do not raise.

    The report's .score (supported / all), .label and .unsupported are computed for you.
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
