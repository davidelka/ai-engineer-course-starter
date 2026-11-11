"""M9: the evaluation's two building blocks (mine.align, mine.relevance)."""

import pytest

from jobagent.models import CategoryScore, JobPosting
from mine import align, relevance


def P(title, cat="backend"):
    return JobPosting(title=title, categories=[CategoryScore(category=cat, confidence=0.9)])


def G(title, cat="backend"):
    return {"title": title, "primary_category": cat}


def test_align_matches_by_title():
    preds = [P("Frontend Developer", "frontend"), P("Backend Engineer")]
    out = align(preds, [G("Backend Engineer"), G("Frontend Developer", "frontend")])
    assert out == [preds[1], preds[0]]


def test_align_each_prediction_used_once():
    preds = [P("Backend Engineer")]
    out = align(preds, [G("Backend Engineer"), G("Senior Backend Engineer")])
    assert out == [preds[0], None]


def test_align_category_bonus_breaks_a_title_tie():
    preds = [P("Engineer", "backend"), P("Engineer", "devops")]
    out = align(preds, [G("Engineer", "devops")])
    assert out == [preds[1]]


def test_align_empty():
    assert align([], [G("Backend Engineer")]) == [None]
    assert align([P("Backend Engineer")], []) == []


def test_relevance_two_views():
    pred = ["match", "maybe", "other", "match", "other"]
    gold = ["match", "match", "maybe", "other", "other"]
    r = relevance(pred, gold)
    assert (r["match"]["tp"], r["match"]["fp"], r["match"]["fn"]) == (1, 1, 1)
    assert (r["shown"]["tp"], r["shown"]["fp"], r["shown"]["fn"]) == (2, 1, 1)
    assert r["match"]["precision"] == pytest.approx(0.5)
    assert r["tier_accuracy"] == pytest.approx(2 / 5)


def test_relevance_empty():
    r = relevance([], [])
    assert r["tier_accuracy"] == 0.0
    assert r["match"]["precision"] == 1.0 and r["match"]["recall"] == 1.0
