"""M8: answer_metrics (mine.py). The per-question numbers the evaluation averages."""

import pytest

from mine import answer_metrics

KEYS = {"context_recall", "citation_precision", "citation_recall", "stale_cited", "abstain_ok"}


def Q(sources, stale=()):
    return {"id": "q", "source_ids": list(sources), "tags": [f"stale:{d}" for d in stale] + ["type:x"]}


def test_keys():
    assert set(answer_metrics(Q(["a"]), ["a"], ["a"], False)) == KEYS


def test_answerable_perfect():
    m = answer_metrics(Q(["a", "b"]), ["a", "b", "c"], ["a", "b"], False)
    assert m == {"context_recall": 1.0, "citation_precision": 1.0, "citation_recall": 1.0,
                 "stale_cited": False, "abstain_ok": True}


def test_answerable_partial():
    m = answer_metrics(Q(["a", "b"]), ["a", "c"], ["a", "c", "c"], False)
    assert m["context_recall"] == pytest.approx(0.5)
    assert m["citation_precision"] == pytest.approx(0.5)        # a and c, c counts once
    assert m["citation_recall"] == pytest.approx(0.5)


def test_nothing_cited_is_zero_precision():
    m = answer_metrics(Q(["a"]), ["a"], [], False)
    assert m["citation_precision"] == 0.0 and m["citation_recall"] == 0.0


def test_refusing_an_answerable_question_is_wrong():
    assert answer_metrics(Q(["a"]), ["a"], [], True)["abstain_ok"] is False


def test_unanswerable():
    ok = answer_metrics(Q([]), ["x"], [], True)
    assert ok["abstain_ok"] is True
    assert ok["context_recall"] is None and ok["citation_precision"] is None and ok["citation_recall"] is None
    assert answer_metrics(Q([]), ["x"], ["x"], False)["abstain_ok"] is False


def test_stale_citation():
    m = answer_metrics(Q(["hr-vacation-2026"], stale=["hr-vacation-2024"]), ["hr-vacation-2024"],
                       ["hr-vacation-2024"], False)
    assert m["stale_cited"] is True and m["citation_precision"] == 0.0
