"""Exercise 2: p95 latency budget with parallel groups."""

import pytest

from archkit import latency as ref
from archkit.latency import Stage
from mine import latency_budget


def test_docstring_example():
    r = latency_budget([Stage("A", 100), Stage("B", 300, group="g"), Stage("C", 200, group="g"), Stage("D", 50)], 500)
    assert r["blocks"] == [("A", 100), ("g", 300), ("D", 50)]
    assert r["total_p95_ms"] == 450
    assert r["slack_ms"] == 50 and r["within_budget"] is True
    assert r["largest"] == "g"
    assert r["budget_ms"] == 500


def test_over_budget():
    r = latency_budget([Stage("llm", 6000), Stage("guard", 300)], 5000)
    assert r["within_budget"] is False and r["slack_ms"] == -1300 and r["largest"] == "llm"


def test_group_position_is_first_member():
    r = latency_budget([Stage("x", 10, group="p"), Stage("y", 5), Stage("z", 30, group="p")], 100)
    assert r["blocks"] == [("p", 30), ("y", 5)]


def test_shares_sum_to_one():
    r = latency_budget([Stage("a", 100), Stage("b", 300)], 1000)
    assert r["shares"] == pytest.approx({"a": 0.25, "b": 0.75})


def test_empty():
    r = latency_budget([], 1000)
    assert r["blocks"] == [] and r["total_p95_ms"] == 0 and r["largest"] is None and r["within_budget"] is True


def test_matches_reference_on_company_brain(company_brain):
    for p in company_brain.budget.paths:
        st = ref.stages_from_spec(p)
        mine, want = latency_budget(st, p.latency_budget_ms), ref.latency_budget(st, p.latency_budget_ms)
        assert mine["blocks"] == want["blocks"] and mine["largest"] == want["largest"]
        assert mine["total_p95_ms"] == pytest.approx(want["total_p95_ms"])
