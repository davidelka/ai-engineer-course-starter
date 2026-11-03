"""Exercise 8: your design review finds most planted problems, without crying wolf."""

import sys
from pathlib import Path

import yaml

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
from check_review import score  # noqa: E402

REVIEW = yaml.safe_load((LAB / "designs" / "my_review.yaml").read_text(encoding="utf-8")) or {}
S = score(REVIEW)


def test_finds_at_least_six_of_eight():
    n = len(S["found"]) + len(S["partial"])
    assert n >= 6, f"found {n} of 8 planted problems"


def test_names_the_right_checklist_item_for_most():
    assert len(S["found"]) >= 5, f"only {len(S['found'])} findings name the main checklist item"


def test_at_most_two_false_positives():
    assert len(S["false_positives"]) <= 2, f"false positives: {S['false_positives']}"


def test_every_finding_has_a_problem_and_a_fix():
    assert not S["problems"], S["problems"]
