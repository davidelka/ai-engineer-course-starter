"""Exercise 2: fact_covered, fact_coverage and citation_scores in mine.py."""

import pytest

import mine
from evalkit import metrics as ref


# ---------------------------------------------------------------- fact_covered
@pytest.mark.parametrize("answer, fact, expected", [
    ("Up to 5 days carry over [1].", "up to 5 days can be carried over", True),
    ("Up to 3 days carry over.", "up to 5 days can be carried over", False),            # number missing
    ("Carried-over days expire on March 31.", "carried-over days expire on March 31", True),
    ("They expire at the end of March.", "carried-over days expire on March 31", False),  # 31 missing
    ("The total overcharge was €48,900.", "€48,900 in total", True),                     # "48,900" -> "48900"
    ("It costs 3000 NIS.", "3,000 NIS", True),
    ("Handover is on Sunday at 10:00.", "weekly handover Thursday 10:00", False),          # 1 of 3 words
    ("The Identity team owns it.", "Identity team", True),
    ("Gil Avraham leads it.", "Gil Avraham", True),
    ("מקבלים 14 ימים של חופשה", "14 ימים", True),
    ("מקבלים 14 ימי חופשה", "14 ימים", False),                                           # "ימי" is not "ימים": a lexical limit
    ("החניה בקומה מינוס 2, 18 מקומות", "18 מקומות", True),
    ("ההזמנה באפליקציה של הבניין", "באפליקציית החניה", False),
    ("בחניון יש מקום", "חניון", True),                                                    # Hebrew prefix ב
    ("SMS codes are accepted", "SMS codes are no longer accepted", True),                 # the known blind spot: negation
])
def test_fact_covered_cases(answer, fact, expected):
    assert mine.fact_covered(answer, fact) == expected


def test_fact_covered_plural_variant():
    assert mine.fact_covered("Two days off.", "days") is True
    assert mine.fact_covered("One day off.", "days") is True          # "days" -> "day"


def test_fact_covered_threshold():
    a = "Identity team"
    f = "Identity team led by Gil Avraham"   # words: identity team led gil avraham -> 2/5
    assert mine.fact_covered(a, f, 0.4) is True
    assert mine.fact_covered(a, f, 0.5) is False


def test_fact_covered_no_words_no_numbers():
    assert mine.fact_covered("Answer: z", "z") is True    # substring rule ("z" is too short to be a word)
    assert mine.fact_covered("Answer: b", "z") is False


# ---------------------------------------------------------------- fact_coverage
def test_fact_coverage_basic():
    facts = ["up to 5 days can be carried over", "carried-over days expire on March 31"]
    assert mine.fact_coverage("Up to 5 days carry over; carried-over days expire on March 31.", facts) == 1.0
    assert mine.fact_coverage("Up to 5 days carry over.", facts) == 0.5
    assert mine.fact_coverage("not in the documents", facts) == 0.0
    assert mine.fact_coverage("anything", []) is None


def test_fact_coverage_matches_reference_on_baseline(golden, baseline_outputs):
    """Your coverage must equal the reference on all 69 answerable golden questions."""
    diffs = []
    for rec in baseline_outputs.records:
        ex = golden[rec.example_id]
        facts = ex.expected["answer_facts"]
        if not facts:
            continue
        a = rec.output["answer"]
        if mine.fact_coverage(a, facts) != ref.fact_coverage(a, facts):
            diffs.append((ex.id, mine.fact_coverage(a, facts), ref.fact_coverage(a, facts)))
    assert not diffs, f"differs from the reference on: {diffs[:5]}"


# ---------------------------------------------------------------- citation_scores
def test_citations_answerable():
    assert mine.citation_scores(["hr-vacation-2026"], ["hr-vacation-2026"], ["hr-vacation-2024"]) == \
        {"precision": 1.0, "recall": 1.0, "stale": False}
    assert mine.citation_scores(["hr-vacation-2024", "hr-vacation-2026"], ["hr-vacation-2026"], ["hr-vacation-2024"]) == \
        {"precision": 0.5, "recall": 1.0, "stale": True}
    assert mine.citation_scores([], ["a"]) == {"precision": 0.0, "recall": 0.0, "stale": False}


def test_citations_multi_source_and_duplicates():
    s = mine.citation_scores(["eng-pm-2026-08-api", "eng-pm-2026-08-api"], ["eng-pm-2026-08-api", "eng-service-catalog"])
    assert s == {"precision": 1.0, "recall": 0.5, "stale": False}


def test_citations_unanswerable():
    assert mine.citation_scores([], []) == {"precision": 1.0, "recall": 1.0, "stale": False}
    assert mine.citation_scores(["co-offices"], []) == {"precision": 0.0, "recall": 0.0, "stale": False}


def test_citations_match_reference_on_baseline(golden, baseline_outputs):
    for rec in baseline_outputs.records:
        e = golden[rec.example_id].expected
        args = (rec.output["cited_docs"], e["source_ids"], e["stale_ids"])
        assert mine.citation_scores(*args) == ref.citation_scores(*args), rec.example_id
