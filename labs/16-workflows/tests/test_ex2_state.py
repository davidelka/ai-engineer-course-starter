"""Exercise 2: reducers (how node updates merge into the state) and routing functions."""
import mine
from flowkit import runner, store


def test_merge_audit_appends_and_dedupes():
    left = [{"id": "a", "n": 1}]
    out = mine.merge_audit(left, [{"id": "b"}, {"id": "a", "n": 2}, {"id": "b"}, {"id": "c"}])
    assert [e["id"] for e in out] == ["a", "b", "c"]
    assert out[0]["n"] == 1  # the first copy wins
    assert left == [{"id": "a", "n": 1}]  # not mutated


def test_merge_audit_accepts_one_event_and_none():
    assert mine.merge_audit(None, {"id": "x"}) == [{"id": "x"}]
    assert mine.merge_audit([{"id": "x"}], None) == [{"id": "x"}]
    assert mine.merge_audit(None, None) == []


def test_add_usage():
    out = mine.add_usage({"calls": 1, "cost_usd": 0.1}, {"calls": 2, "input_tokens": 5})
    assert out == {"calls": 3, "input_tokens": 5, "output_tokens": 0, "cost_usd": 0.1}
    assert mine.add_usage(None, None) == {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    a = {"calls": 1}
    mine.add_usage(a, {"calls": 1})
    assert a == {"calls": 1}
    assert isinstance(mine.add_usage({"calls": 1}, {})["cost_usd"], float)


def test_route_after_file():
    assert mine.route_after_file({"status": "approved"}) == "notify"
    assert mine.route_after_file({"status": "pending_manager"}) == "manager_approval"
    assert mine.route_after_file({"status": "pending_security"}) == "risk_summary"
    assert mine.route_after_file({"status": "failed"}) == "notify"


def test_route_after_gate():
    assert mine.route_after_gate({"gate_error": {"gate": "manager", "message": "x"}}) == "manager_approval"
    assert mine.route_after_gate({"gate_error": {"gate": "security", "message": "x"},
                                  "decision": {"gate": "security", "decision": "approve"}}) == "security_approval"
    assert mine.route_after_gate({"gate_error": None,
                                  "decision": {"gate": "manager", "decision": "timeout"}}) == "escalate"
    assert mine.route_after_gate({"decision": {"gate": "security", "decision": "timeout"}}) == "apply_decision"
    assert mine.route_after_gate({"decision": {"gate": "manager", "decision": "reject"}}) == "apply_decision"


def test_graph_runs_with_your_reducers_and_routes(lab):
    app = lab.app("ex2")
    out = lab.run(app, "g1", "r1")  # Jira read: auto_approve, straight to notify
    assert out["status"] == "approved" and out["done"]
    st = app.get_state(runner.config("g1")).values
    ids = [e["id"] for e in st["audit"]]
    assert len(ids) == len(set(ids)) == 4  # extracted, enriched, routed, approved
    assert st["usage"]["calls"] == 1
    out = lab.run(app, "g2", "r4")  # aws admin: risk summary, then the security gate
    assert out["paused_at_gate"] and out["gate"]["gate"] == "security"
    assert app.get_state(runner.config("g2")).values["usage"]["calls"] == 2  # intake + risk summary
    assert len(store.dump(lab.db)["access_requests"]) == 2
