"""Milestone 9: request_rows and slo_report, from exported spans (mine.py)."""
import pytest

from _impl import mine


def span(tid, sid, parent=None, *, start=0.0, dur=100.0, status="OK", **attrs):
    return {"trace_id": tid, "span_id": sid, "parent_id": parent, "name": sid, "start_ms": start,
            "duration_ms": dur, "status": status, "attributes": attrs}


def chat(tid, sid, parent, cost, start=50.0):
    return span(tid, sid, parent, start=start, **{"gen_ai.operation.name": "chat", "obskit.cost_usd": cost})


SPANS = [
    span("t1", "r1", start=10, dur=1200, **{"brain.request_type": "ask", "brain.intent": "knowledge"}),
    chat("t1", "c1", "r1", 0.001), chat("t1", "c2", "r1", 0.002),
    span("t2", "r2", start=5, dur=9000, **{"brain.request_type": "ask", "brain.intent": "knowledge"}),
    chat("t2", "c3", "r2", 0.004),
    span("t3", "r3", start=20, dur=50, status="ERROR", **{"brain.request_type": "ask"}),
    span("t4", "r4", start=30, dur=2000, **{"brain.request_type": "request", "brain.intent": "access_request"}),
    span("t5", "r5", start=1, dur=10),                                     # not a brain request
]


def test_request_rows():
    rows = mine.request_rows(SPANS)
    assert [r["trace_id"] for r in rows] == ["t2", "t1", "t3", "t4"]        # sorted by start, t5 skipped
    r1 = next(r for r in rows if r["trace_id"] == "t1")
    assert r1["type"] == "ask" and r1["duration_ms"] == 1200 and r1["error"] is False
    assert r1["llm_calls"] == 2 and r1["spans"] == 3 and r1["intent"] == "knowledge"
    assert r1["cost_usd"] == pytest.approx(0.003)
    assert next(r for r in rows if r["trace_id"] == "t3")["error"] is True


def test_slo_report():
    rep = mine.slo_report(SPANS)
    assert rep["requests"] == 4 and list(rep["by_type"]) == ["ask", "request"]
    a = rep["by_type"]["ask"]
    assert a["n"] == 3 and a["errors"] == 1
    assert a["availability"] == pytest.approx(2 / 3) and a["availability_ok"] is False
    assert a["latency_target_ms"] == 8000.0 and a["latency_sli"] == pytest.approx(0.5)   # 1200 ok, 9000 slow
    assert a["latency_ok"] is False                                                      # p95 over the target
    assert a["cost_total_usd"] == pytest.approx(0.007) and a["cost_mean_usd"] == pytest.approx(0.007 / 3)
    assert a["cost_target_usd"] == 0.005 and a["cost_ok"] is True
    assert a["llm_calls_mean"] == pytest.approx(1.0)
    r = rep["by_type"]["request"]
    assert r["availability_ok"] is True and r["p50_ms"] == 2000 and r["latency_ok"] is True


def test_empty():
    assert mine.slo_report([]) == {"requests": 0, "by_type": {}}
