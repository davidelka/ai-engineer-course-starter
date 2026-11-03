"""Exercise 8: graph-level contract tests with ALL your parts (ex2 + ex3 + ex5) and a fake LLM.

SPEC-006 (labs/06-spec-driven/spec/access-requests.spec.md) is the workflow's contract.
Each test names the requirement it checks. Add your own tests at the bottom (see README).
"""
import pytest

from flowkit import FakeLLM, runner, store
from flowkit.faults import with_faults
from toolkit import acme_registry

ALL = ("ex2", "ex3", "ex5")


@pytest.mark.parametrize("sid", ["r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8"])
def test_every_sample_lands_where_the_policy_says(lab, sid):  # REQ-4 (with policy v2.2) and REQ-5
    app = lab.app(*ALL)
    out = lab.run(app, sid, sid)
    s = lab.samples[sid]
    assert (out["status"], out["route"]) == (s["expect_status"], s["expect_route"])
    if out["request_id"]:
        assert store.get_request(lab.db, out["request_id"])["status"] == s["expect_status"]


def test_nothing_that_needs_a_human_is_approved_without_one(lab):  # spec section 1, success criteria
    app = lab.app(*ALL)
    for sid in lab.samples:
        lab.run(app, sid, sid)
    for r in store.dump(lab.db)["access_requests"]:
        if r["status"] == "approved":
            assert r["route"] == "auto_approve" and r["approver"] == "system:auto"


def test_audit_records_every_status_change(lab):  # REQ-11
    app = lab.app(*ALL)
    lab.run(app, "c1", "r2")
    lab.decide(app, "c1", "approve", "E005", "ok")
    rows = store.dump(lab.db, "c1")["audit"]
    assert [(r["from_status"], r["to_status"], r["actor"]) for r in rows] == [
        (None, "pending_manager", "system"), ("pending_manager", "approved", "E005")]


def test_closed_requests_stay_closed(lab):  # REQ-10
    app = lab.app(*ALL)
    lab.run(app, "c2", "r2")
    lab.decide(app, "c2", "reject", "E005", "not this quarter")
    before = store.dump(lab.db, "c2")
    lab.decide(app, "c2", "approve", "E063", "")
    assert store.dump(lab.db, "c2") == before


def test_tool_timeout_is_retried_by_the_node(lab):
    reg = with_faults(acme_registry(requests_db=lab.db), {"check_policy": ("timeout", 2)}, delay_s=0.3, timeout_s=0.05)
    app = lab.app(*ALL, registry=reg)
    out = lab.run(app, "c3", "r1")
    assert out["status"] == "approved" and reg.fault_counts["check_policy"] == 3


def test_unreadable_request_asks_for_info(lab):
    app = lab.app(*ALL, llm=FakeLLM(replies=["not json", "still not json"]))
    out = lab.run(app, "c4", "r1")
    assert out["status"] == "needs_info" and out["done"]
    assert "could not" in store.dump(lab.db, "c4")["outbox"][0]["body"].lower()


# ---------------------------------------------------------------- your tests (exercise 8)
# Write at least these two, then remove the skip markers:
@pytest.mark.skip(reason="exercise 8: write this test")
def test_escalated_request_is_decided_by_security(lab):
    """r5 (Notion, needs_manager): SLA timeout at the manager gate -> security gate;
    a security engineer approves -> status approved, approver is that engineer, and the
    audit has three rows: new->pending_manager, pending_manager->pending_security, ->approved."""


@pytest.mark.skip(reason="exercise 8: write this test")
def test_fork_reruns_side_effects(lab):
    """r2 paused at the manager gate. Fork from the checkpoint whose next node is policy with
    access_level='viewer' (app.update_state + app.stream(None, fork_config)). Assert the thread
    now ends approved AND that the requests DB holds TWO records for Dana (time travel re-ran
    file_request with a new idempotency key). Then write down in the README answer what a
    production system should do about the first, still pending, record."""
