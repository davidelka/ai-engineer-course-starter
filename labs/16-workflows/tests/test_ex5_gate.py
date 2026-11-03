"""Exercise 5: the approval gate (interrupt / resume) and its authority rules (SPEC-006 REQ-8, REQ-9)."""
from flowkit import runner, store


def test_pause_shows_the_request_to_the_approver(lab):
    app = lab.app("ex5")
    out = lab.run(app, "a1", "r2")  # Dana Levi, Figma editor
    assert out["paused_at_gate"] and out["next"] == ["manager_approval"]
    g = out["gate"]
    assert g["gate"] == "manager" and g["system"] == "figma" and g["access_level"] == "editor"
    assert any("E005" in a for a in g["allowed_approvers"])


def test_manager_approves(lab):
    app = lab.app("ex5")
    lab.run(app, "a2", "r2")
    out = lab.decide(lab.app("ex5"), "a2", "approve", "michal.ben-david@acme.example", "  ok  ")  # a "new process"
    assert out["status"] == "approved" and out["done"]
    d = app.get_state(runner.config("a2")).values["decision"]
    assert d == {"gate": "manager", "decision": "approve", "actor_id": "E005", "actor_name": "Michal Ben-David",
                 "comment": "ok"}
    assert store.get_request(lab.db, out["request_id"])["approver"] == "E005"


def test_refusals_keep_the_gate_closed(lab):
    app = lab.app("ex5")
    lab.run(app, "a3", "r2")
    cases = [("maybe", "E005", "x", "decision"),
             ("approve", "nobody@acme.example", "", "unknown"),
             ("approve", "dana.levi@acme.example", "", "own request"),  # AC-9.3
             ("approve", "E009", "", "manager"),                         # not her manager
             ("reject", "E005", "", "comment")]
    for decision, actor, comment, word in cases:
        out = lab.decide(app, "a3", decision, actor, comment)
        assert out["paused_at_gate"], (decision, actor)
        assert word in out["gate"]["previous_error"], out["gate"]["previous_error"]
        assert store.get_request(lab.db, out["request_id"])["status"] == "pending_manager"
    out = lab.decide(app, "a3", "approve", "E063")  # AC-8.3: security may decide needs_manager
    assert out["status"] == "approved"


def test_security_gate(lab):
    app = lab.app("ex5")
    out = lab.run(app, "a4", "r4")  # aws-production admin
    assert out["gate"]["gate"] == "security" and out["gate"]["risk_summary"]
    out = lab.decide(app, "a4", "approve", "E005")  # AC-9.1: a manager cannot
    assert "only the security team" in out["gate"]["previous_error"]
    out = lab.decide(app, "a4", "reject", "E064", "use the scoped migration role")
    assert out["status"] == "rejected"


def test_timeouts_escalate_then_expire(lab):
    app = lab.app("ex5")
    lab.run(app, "a5", "r5")  # Notion member: needs_manager (manager E074)
    out = lab.decide(app, "a5", "timeout", "system")
    assert out["paused_at_gate"] and out["gate"]["gate"] == "security"
    out = lab.decide(app, "a5", "timeout", "system")
    assert out["status"] == "expired"
