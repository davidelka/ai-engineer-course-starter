"""Exercise 1: the stage classifier. Every case is in fixtures/cases.jsonl with the reason."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

import mine
from ragkit.diagnose import STAGES, Case

ROWS = [json.loads(x) for x in (Path(__file__).resolve().parent.parent / "fixtures" / "cases.jsonl")
        .read_text(encoding="utf-8").splitlines() if x.strip()]


@pytest.mark.parametrize("row", ROWS, ids=[r["name"] for r in ROWS])
def test_constructed_case(row):
    got = mine.classify_failure(Case(**row["case"]))
    assert got == row["expected"], f"{row['name']}: expected {row['expected']} ({row['why']}), got {got}"


def test_every_label_is_known(cases):
    for name, _, case, _ in cases:
        assert mine.classify_failure(case) in ("ok",) + STAGES, name


def test_docstring_examples():
    assert mine.classify_failure(Case(source_ids=["a"], quote_status=["covered"], candidates=["a", "b"],
                                      context=["b"], cited=["b"], fact_coverage=0.0)) == "ranked_low"
    assert mine.classify_failure(Case(source_ids=[], abstained=False)) == "failed_to_refuse"
    assert mine.classify_failure(Case(source_ids=[], abstained=True)) == "ok"


def base():
    return Case(qid="x", source_ids=["a"], quote_status=["covered"], candidates=["a", "b"], context=["a", "b"],
                evidence_positions=[1], context_tokens=800, answer="...", cited=["a"], fact_coverage=1.0,
                grounded=True)


def test_upstream_stage_wins_over_downstream_symptoms():
    # the quote is split AND the answer cites a stale doc AND is ungrounded: chunking is the root cause
    c = replace(base(), quote_status=["covered", "split"], cited=["old"], stale_ids=["old"], grounded=False)
    assert mine.classify_failure(c) == "chunk_split"
    c = replace(base(), quote_status=["split", "missing"])
    c = replace(c, fact_coverage=0.0)
    assert mine.classify_failure(c) == "extraction_lost"          # missing is checked before split
    c = replace(base(), quote_status=["missing", "no_doc"], fact_coverage=0.0)
    assert mine.classify_failure(c) == "missing_from_corpus"


def test_every_source_counts_for_multi_hop():
    c = replace(base(), source_ids=["a", "c"], quote_status=["covered", "covered"], fact_coverage=0.0)
    assert mine.classify_failure(c) == "not_retrieved"            # "c" is not among the candidates
    c = replace(c, candidates=["a", "b", "c"])
    assert mine.classify_failure(c) == "ranked_low"               # retrieved, but not in the prompt
    c = replace(c, context=["a", "c"])
    assert mine.classify_failure(c) == "ignored_context"


def test_thresholds_are_parameters():
    c = replace(base(), fact_coverage=0.6)
    assert mine.classify_failure(c) == "ok"
    assert mine.classify_failure(c, min_facts=0.8) == "ignored_context"
    long = replace(base(), context=["x", "a", "y", "z"], evidence_positions=[2], context_tokens=3000,
                   fact_coverage=0.0)
    assert mine.classify_failure(long) == "ignored_context"       # 3000 < 4000: not "long"
    assert mine.classify_failure(long, long_context=2500) == "lost_in_middle"


def test_lost_in_middle_needs_every_position_in_the_middle():
    c = replace(base(), context=["x", "a", "y", "a"], evidence_positions=[2, 4], context_tokens=9000,
                fact_coverage=0.0)
    assert mine.classify_failure(c) == "ignored_context"          # position 4 is the LAST one
    c = replace(c, evidence_positions=[2, 3])
    assert mine.classify_failure(c) == "lost_in_middle"
    c = replace(c, evidence_positions=[])
    assert mine.classify_failure(c) == "ignored_context"


def test_none_means_not_measured():
    c = replace(base(), fact_coverage=None, grounded=None)
    assert mine.classify_failure(c) == "ok"
    c = replace(base(), cited=[], answer="Up to 5 days.")
    assert mine.classify_failure(c) == "wrong_citation"           # answered without citing anything
    c = replace(base(), abstained=True, cited=[], fact_coverage=None)
    assert mine.classify_failure(c) == "false_refusal"            # abstaining is a failure by itself
