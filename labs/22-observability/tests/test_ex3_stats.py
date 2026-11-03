"""Exercise 3: percentiles, latency per span type, cost per trace, slowest traces."""

import pytest

from conftest import mk
from mine import percentile, summarize
from obskit.analyze import summarize as ref_summarize


def test_percentile_interpolates():
    assert percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert percentile([4, 1, 3, 2], 0) == 1 and percentile([4, 1, 3, 2], 100) == 4
    assert percentile([10], 95) == 10
    assert percentile(list(range(1, 101)), 95) == pytest.approx(95.05)


def test_percentile_rejects_bad_input():
    with pytest.raises(ValueError):
        percentile([], 50)
    with pytest.raises(ValueError):
        percentile([1, 2], 101)


def small():
    return [
        mk("t1", "a", "invoke_workflow acme_answer", 0, 1000, **{"obskit.span.type": "agent"}),
        mk("t1", "b", "retrieval acme-kb", 5, 20, parent="a", **{"gen_ai.operation.name": "retrieval"}),
        mk("t1", "c", "chat m", 30, 900, parent="a", **{"gen_ai.operation.name": "chat", "obskit.cost_usd": 0.002}),
        mk("t2", "d", "invoke_workflow acme_answer", 5000, 3000, **{"obskit.span.type": "agent"}),
        mk("t2", "e", "chat m", 5010, 1000, parent="d", status="ERROR", **{"obskit.span.type": "llm"}),
        mk("t2", "f", "chat m", 6100, 1800, parent="d", **{"obskit.span.type": "llm", "obskit.cost_usd": 0.001}),
        mk("t2", "g", "custom step", 7950, 10, parent="d"),
    ]


def test_types_and_counts():
    s = summarize(small())
    assert s["spans"] == 7 and s["traces"] == 2
    assert list(s["by_type"]) == sorted(s["by_type"]) == ["agent", "llm", "other", "retrieval"]
    llm = s["by_type"]["llm"]
    assert llm["count"] == 3 and llm["errors"] == 1 and llm["max_ms"] == 1800
    assert llm["p50_ms"] == pytest.approx(1000)


def test_per_trace_cost_and_error():
    s = summarize(small())
    t1, t2 = s["per_trace"]["t1"], s["per_trace"]["t2"]
    assert t1["cost_usd"] == pytest.approx(0.002) and t1["llm_calls"] == 1 and t1["error"] is False
    assert t2["cost_usd"] == pytest.approx(0.001) and t2["llm_calls"] == 2 and t2["error"] is True
    assert t2["duration_ms"] == 3000 and t1["name"] == "invoke_workflow acme_answer"
    assert s["cost"]["total_usd"] == pytest.approx(0.003)
    assert s["cost"]["mean_per_trace_usd"] == pytest.approx(0.0015)


def test_slowest_first():
    s = summarize(small(), top_n=1)
    assert s["slowest"] == [{"trace_id": "t2", "name": "invoke_workflow acme_answer", "duration_ms": 3000}]
    assert s["latency"]["p50_ms"] == pytest.approx(2000)


def test_matches_reference_on_the_forensic_set(forensic):
    mine, ref = summarize(forensic, top_n=5), ref_summarize(forensic, top_n=5)
    assert mine["traces"] == ref["traces"] == 12
    assert set(mine["by_type"]) == set(ref["by_type"])
    for t in ref["by_type"]:
        for k in ("count", "errors", "p50_ms", "p95_ms", "max_ms"):
            assert mine["by_type"][t][k] == pytest.approx(ref["by_type"][t][k]), (t, k)
    assert [r["trace_id"] for r in mine["slowest"]] == [r["trace_id"] for r in ref["slowest"]]
    assert mine["cost"]["p95_per_trace_usd"] == pytest.approx(ref["cost"]["p95_per_trace_usd"])
