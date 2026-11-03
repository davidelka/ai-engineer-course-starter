"""M6: route_question (mine.py), on the rules and on the two labeled sets."""

import json
from pathlib import Path

import pytest

from mine import route_question

DATA = [json.loads(x) for x in (Path(__file__).resolve().parent.parent / "data" / "data_questions.jsonl")
        .read_text(encoding="utf-8").splitlines() if x.strip()]


def test_example_data_question():
    r = route_question("How many open P1 tickets do we have right now?")
    assert r.kind == "data" and r.reason == "aggregate over a table entity"
    assert r.matched == ["how many", "tickets", "p1"]


@pytest.mark.parametrize("q", ["How many sick days do employees in Israel accrue per year?",
                               "Why did the August outage happen?", "What is the refund policy for annual plans?",
                               "Can I use SMS codes as my second factor?", "איך מזמינים חניה בתל אביב?"])
def test_doc_cues_win(q):
    r = route_question(q)
    assert r.kind == "docs" and r.reason == "policy/process wording" and r.matched


@pytest.mark.parametrize("q", ["What is a Red Folder account?", "How many vacation days can I carry over?",
                               "What is the API rate limit for a Business plan customer?",
                               "How many people are in the team that owns billing-service?"])
def test_no_aggregate_entity_pair_goes_to_docs(q):
    assert route_question(q).kind == "docs"


def test_normalizes_case_and_spaces():
    assert route_question("  HOW   MANY\ncustomers are on each plan? ").kind == "data"


def test_hebrew_data():
    r = route_question("כמה קריאות P1 פתוחות יש כרגע?")
    assert r.kind == "data" and "כמה" in r.matched and "קריאות" in r.matched


def test_all_data_questions_go_to_data():
    wrong = [d["question"] for d in DATA if route_question(d["question"]).kind != "data"]
    assert not wrong


def test_golden_questions_mostly_go_to_docs():
    from ragkit.acme import acme_qa
    wrong = [q["id"] for q in acme_qa() if route_question(q["question"]).kind != "docs"]
    # a few numeric questions mention customers/employees with "how many": they go to the
    # database first and FALL BACK to the documents when the SQL planner says "not answerable"
    assert len(wrong) <= 5, wrong
