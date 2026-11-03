"""Environment tests for flowkit (lesson 16): the access-request workflow on LangGraph.

Skipped cleanly when langgraph / langgraph-checkpoint-sqlite are not installed
(pip install -r labs/16-workflows/requirements.txt).
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langgraph.checkpoint.sqlite")

from langgraph.types import Command, RetryPolicy  # noqa: E402

from flowkit import FakeLLM, add_usage, heuristic_extract, merge_audit  # noqa: E402
from flowkit import runner, store  # noqa: E402
from flowkit.faults import parse_fault, with_faults  # noqa: E402
from flowkit.graph import build_graph, open_checkpointer  # noqa: E402
from flowkit.nodes import Deps, route_after_file, route_after_gate  # noqa: E402
from llmkit.errors import LLMError  # noqa: E402
from toolkit import acme_registry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = [json.loads(line) for line in (ROOT / "labs/16-workflows/data/requests.jsonl").read_text().splitlines()]
FAST_RETRY = RetryPolicy(max_attempts=3, initial_interval=0.01, jitter=False, retry_on=__import__(
    "flowkit.nodes", fromlist=["ToolUnavailable"]).ToolUnavailable)
T0 = "2026-11-02T08:00:00+00:00"


@pytest.fixture
def env(tmp_path):
    db, cp = tmp_path / "requests.db", tmp_path / "checkpoints.db"

    def make(llm=None, registry=None, **kw):
        deps = Deps(llm=llm or FakeLLM(), registry=registry or acme_registry(requests_db=db), requests_db=db,
                    clock=lambda: T0, **kw)
        saver = open_checkpointer(cp)
        return build_graph(deps, checkpointer=saver, retry=FAST_RETRY), saver, deps
    make.db, make.cp = db, cp
    return make


def run(app, tid, requester, text):
    list(runner.start(app, tid, requester, text, T0))
    return runner.summary(app, tid)


def decide(app, tid, decision, actor, comment=""):
    list(runner.resume(app, tid, {"decision": decision, "actor": actor, "comment": comment}))
    return runner.summary(app, tid)


SAMPLE = {s["id"]: s for s in SAMPLES}


# ---------------------------------------------------------------- pure parts
def test_reducers():
    a = [{"id": "x"}]
    assert merge_audit(a, [{"id": "x"}, {"id": "y"}]) == [{"id": "x"}, {"id": "y"}]
    assert merge_audit(None, {"id": "z"}) == [{"id": "z"}] and a == [{"id": "x"}]
    assert merge_audit(a, None) == a
    u = add_usage({"calls": 1, "input_tokens": 10, "cost_usd": 0.1}, {"calls": 2, "output_tokens": 5, "cost_usd": 0.2})
    assert u == {"calls": 3, "input_tokens": 10, "output_tokens": 5, "cost_usd": pytest.approx(0.3)}
    assert add_usage(None, None)["calls"] == 0


def test_routing_functions():
    assert route_after_file({"status": "approved"}) == "notify"
    assert route_after_file({"status": "pending_manager"}) == "manager_approval"
    assert route_after_file({"status": "pending_security"}) == "risk_summary"
    assert route_after_gate({"gate_error": {"gate": "security", "message": "x"}}) == "security_approval"
    assert route_after_gate({"decision": {"gate": "manager", "decision": "timeout"}}) == "escalate"
    assert route_after_gate({"decision": {"gate": "security", "decision": "timeout"}}) == "apply_decision"
    assert route_after_gate({"decision": {"gate": "manager", "decision": "approve"}, "gate_error": None}) == "apply_decision"


def test_fake_extractor():
    x = heuristic_extract("I need admin on aws-production for 7 days to migrate", "t@acme.example")
    assert (x["system"], x["access_level"], x["duration_days"]) == ("aws-production", "admin", 7)
    assert heuristic_extract("Please add Yossi Cohen to GitHub with read access")["employee"] == "Yossi Cohen"
    assert heuristic_extract("connect an OAuth app to Google Workspace")["external_sharing"] is True
    assert parse_fault("timeout:get_system_info:2") == {"get_system_info": ("timeout", 2)}


# ---------------------------------------------------------------- whole graph, every sample
@pytest.mark.parametrize("s", SAMPLES, ids=[s["id"] for s in SAMPLES])
def test_samples_route_and_pause(env, s):
    app, saver, _ = env()
    out = run(app, s["id"], s["requester"], s["text"])
    assert out["status"] == s["expect_status"]
    assert out["route"] == s["expect_route"]
    assert out["paused_at_gate"] == s["expect_status"].startswith("pending")


def test_auto_approve_audit_and_outbox(env):
    app, _, _ = env()
    s = SAMPLE["r1"]
    out = run(app, "t1", s["requester"], s["text"])
    assert out["done"] and out["status"] == "approved"
    d = store.dump(env.db, "t1")
    assert d["access_requests"][0]["status"] == "approved"
    first = d["audit"][0]  # SPEC-006 AC-11.1
    assert (first["from_status"], first["to_status"], first["actor"]) == (None, "approved", "system")
    assert len(d["outbox"]) == 1
    st = app.get_state(runner.config("t1")).values
    assert len({e["id"] for e in st["audit"]}) == len(st["audit"])
    assert st["usage"]["calls"] == 1  # one LLM call: intake (auto_approve needs no risk summary)


# ---------------------------------------------------------------- approval gates
def test_manager_approves_across_processes(env):
    app, _, _ = env()
    s = SAMPLE["r2"]  # Dana Levi, figma editor -> manager E005
    out = run(app, "t2", s["requester"], s["text"])
    assert out["gate"]["gate"] == "manager" and out["request_id"]
    app2, _, _ = env()  # a new graph object on the same files = a new process
    out = decide(app2, "t2", "approve", "michal.ben-david@acme.example", "ok for the dashboard project")
    assert out["done"] and out["status"] == "approved"
    rec = store.get_request(env.db, out["request_id"])
    assert rec["status"] == "approved" and rec["approver"] == "E005"
    audit = store.dump(env.db, "t2")["audit"]
    assert [(a["from_status"], a["to_status"]) for a in audit] == [(None, "pending_manager"),
                                                                   ("pending_manager", "approved")]


def test_self_approval_and_peer_are_refused(env):
    app, _, _ = env()
    s = SAMPLE["r2"]
    run(app, "t3", s["requester"], s["text"])
    out = decide(app, "t3", "approve", "dana.levi@acme.example")  # REQ-9: own request
    assert out["paused_at_gate"] and "own request" in out["gate"]["previous_error"]
    out = decide(app, "t3", "approve", "E009")  # another team lead, not her manager
    assert out["paused_at_gate"] and "not E016's manager" in out["gate"]["previous_error"]
    out = decide(app, "t3", "reject", "E005")  # rejection without comment
    assert out["paused_at_gate"] and "comment" in out["gate"]["previous_error"]
    out = decide(app, "t3", "approve", "E063")  # security may decide needs_manager (AC-8.3)
    assert out["status"] == "approved"
    assert store.get_request(env.db, out["request_id"])["approver"] == "E063"


def test_security_gate_rules_and_reject(env):
    app, _, _ = env()
    s = SAMPLE["r4"]
    out = run(app, "t4", s["requester"], s["text"])
    assert out["gate"]["risk_summary"]
    out = decide(app, "t4", "approve", "E005")  # a manager cannot approve needs_security (AC-9.1)
    assert out["paused_at_gate"] and "only the security team" in out["gate"]["previous_error"]
    out = decide(app, "t4", "reject", "neta.yosef@acme.example", "use a scoped role, not admin")
    assert out["status"] == "rejected"
    msg = store.dump(env.db, "t4")["outbox"][0]
    assert "rejected" in msg["body"] and "scoped role" in msg["body"]


def test_timeout_escalates_then_expires(env):
    app, _, _ = env()
    s = SAMPLE["r5"]
    run(app, "t5", s["requester"], s["text"])
    out = decide(app, "t5", "timeout", "system")
    assert out["paused_at_gate"] and out["gate"]["gate"] == "security" and out["status"] == "pending_security"
    out = decide(app, "t5", "timeout", "system")
    assert out["status"] == "expired" and out["done"]
    assert store.get_request(env.db, out["request_id"])["status"] == "expired"


def test_external_sharing_raises_the_filed_route(env):
    app, _, _ = env()
    s = SAMPLE["r8"]
    out = run(app, "t8", s["requester"], s["text"])
    rec = store.get_request(env.db, out["request_id"])
    assert rec["status"] == "pending_security" and rec["route"] == "needs_security"


def test_resume_of_a_finished_thread_changes_nothing(env):
    app, _, _ = env()
    s = SAMPLE["r2"]
    run(app, "t6", s["requester"], s["text"])
    decide(app, "t6", "approve", "E005", "ok")
    before = store.dump(env.db, "t6")
    list(runner.resume(app, "t6", {"decision": "reject", "actor": "E063", "comment": "late"}))
    assert store.dump(env.db, "t6") == before  # REQ-10: closed requests stay closed


# ---------------------------------------------------------------- failures, retries, crash and resume
def test_tool_timeout_is_retried(env):
    reg = with_faults(acme_registry(requests_db=env.db), {"get_system_info": ("timeout", 2)},
                      delay_s=0.3, timeout_s=0.05)
    app, _, _ = env(registry=reg)
    s = SAMPLE["r1"]
    out = run(app, "t7", s["requester"], s["text"])
    assert out["status"] == "approved" and reg.fault_counts["get_system_info"] == 3


def test_retries_exhausted_go_to_error_handler(env):
    reg = with_faults(acme_registry(requests_db=env.db), {"get_system_info": ("timeout", 5)},
                      delay_s=0.3, timeout_s=0.05)
    app, _, _ = env(registry=reg)
    s = SAMPLE["r1"]
    out = run(app, "t8", s["requester"], s["text"])
    assert out["status"] == "failed" and "enrich failed after retries" in out["error"]
    assert store.dump(env.db, "t8")["outbox"][0]["subject"].endswith("failed")


def test_llm_failure_in_risk_summary_does_not_block(env):
    app, _, _ = env(llm=FakeLLM(replies=[heuristic_extract_json(SAMPLE["r4"]), LLMError("down", kind="overloaded")]))
    s = SAMPLE["r4"]
    out = run(app, "t9", s["requester"], s["text"])
    assert out["paused_at_gate"] and out["gate"]["risk_summary"].startswith("(LLM unavailable")


def heuristic_extract_json(s):
    return json.dumps(heuristic_extract(s["text"], s["requester"]))


def test_crash_after_side_effect_then_resume_files_once(env, tmp_path):
    script = tmp_path / "crash.py"
    script.write_text(textwrap.dedent(f"""
        import sys; sys.path.insert(0, {str(ROOT)!r})
        from pathlib import Path
        from flowkit import FakeLLM, build_graph, open_checkpointer, Deps
        from flowkit import runner
        from toolkit import acme_registry
        db = Path({str(env.db)!r})
        deps = Deps(llm=FakeLLM(), registry=acme_registry(requests_db=db), requests_db=db, crash_in="file_request")
        app = build_graph(deps, checkpointer=open_checkpointer({str(env.cp)!r}))
        list(runner.start(app, "tc", "dana.levi@acme.example", "I need a Figma editor seat", "t0"))
    """))
    p = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
    assert p.returncode == 137, p.stderr
    assert len(store.dump(env.db)["access_requests"]) == 1  # the side effect happened...
    app, _, _ = env()
    assert runner.summary(app, "tc")["next"] == ["file_request"]  # ...but the checkpoint did not
    list(runner.resume(app, "tc"))
    out = runner.summary(app, "tc")
    assert out["paused_at_gate"]
    assert len(store.dump(env.db)["access_requests"]) == 1  # idempotency key: no duplicate
    assert app.get_state(runner.config("tc")).values["record"]["deduplicated"] is True


# ---------------------------------------------------------------- time travel
def test_fork_before_policy_with_a_lower_level(env):
    app, _, _ = env()
    s = SAMPLE["r2"]
    run(app, "tf", s["requester"], s["text"])
    hist = runner.history(app, "tf")
    before = next(h for h in hist if h["next"] == ["policy"])
    req = dict(before["snapshot"].values["request"], access_level="viewer")
    fork_cfg = app.update_state(before["snapshot"].config, {"request": req})
    list(app.stream(None, fork_cfg, stream_mode="updates"))
    out = runner.summary(app, "tf")
    assert out["status"] == "approved" and out["done"]
    reqs = store.dump(env.db)["access_requests"]
    assert sorted(r["status"] for r in reqs) == ["approved", "pending_manager"]  # the fork filed a second record
    assert len(runner.history(app, "tf")) > len(hist)  # the old checkpoints are still there
