"""Milestone 3: route_metrics (mine.py). Accuracy, per-class precision and recall, errors by direction."""
import pytest

from _impl import mine


def row(i, label, pred, source="rules", llm=False, cost=0.0):
    return {"id": i, "label": label, "pred": pred, "source": source, "llm_called": llm, "cost": cost}


ROWS = [row("r1", "knowledge", "knowledge"), row("r2", "data", "data"),
        row("r3", "access_request", "knowledge", "fallback", True, 0.0001),
        row("r4", "knowledge", "data", "llm", True, 0.0002), row("r5", "access_request", "access_request")]


def test_route_metrics():
    m = mine.route_metrics(ROWS)
    assert m["n"] == 5 and m["accuracy"] == pytest.approx(0.6)
    lo, hi = m["ci95"]
    assert 0 < lo < 0.6 < hi < 1 and round(lo, 3) == lo
    assert m["per_class"]["data"] == {"precision": 0.5, "recall": 1.0, "n": 1}
    assert m["per_class"]["access_request"] == {"precision": 1.0, "recall": 0.5, "n": 2}
    assert m["per_class"]["knowledge"]["precision"] == pytest.approx(0.5)
    assert m["llm_calls"] == 2 and m["llm_rate"] == pytest.approx(0.4)
    assert m["errors_by_direction"] == {"access_request->knowledge": 1, "knowledge->data": 1}
    assert m["cost_usd"] == pytest.approx(0.0003)
    assert m["errors"] == [{"id": "r3", "label": "access_request", "pred": "knowledge", "source": "fallback"},
                           {"id": "r4", "label": "knowledge", "pred": "data", "source": "llm"}]


def test_class_never_predicted_has_no_precision():
    m = mine.route_metrics([row("a", "data", "knowledge")])
    assert m["per_class"]["data"] == {"precision": None, "recall": 0.0, "n": 1}
    assert m["per_class"]["access_request"] == {"precision": None, "recall": None, "n": 0}


def test_empty():
    m = mine.route_metrics([])
    assert m["n"] == 0 and m["accuracy"] == 0.0 and m["llm_rate"] == 0.0 and m["errors"] == []
