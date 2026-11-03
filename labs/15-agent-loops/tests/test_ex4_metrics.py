"""Exercise 4: trajectory metrics on hand-built trajectories, then on real runs."""
import json

import pytest

import mine
from agentkit import AcmeHeuristic, Agent, FakeLLM, load_tasks, with_faults
from toolkit import acme_registry

from pathlib import Path

LAB = Path(__file__).resolve().parent.parent

CREATED = {"id": "AR-00001", "employee_id": "E016", "system": "aws-production", "access_level": "admin",
           "duration_days": 3, "route": "needs_security", "status": "pending_security"}
POLICY = {"system": "aws-production", "access_level": "admin", "route": "needs_security"}
GOLD = {"outcome": "request_created",
        "request": {"employee": "E016", "system": "aws-production", "access_level": "admin", "duration_days": 3,
                    "route": "needs_security"},
        "answer_contains": ["Michal Ben-David"], "required_tools": ["lookup_employee", "check_policy"],
        "optimal_calls": 3}


def call(name, fp, ok=True, text="{}"):
    return {"id": fp, "name": name, "arguments": {}, "fp": fp}, {"id": fp, "name": name, "is_error": not ok,
                                                                  "hash": None if not ok else fp, "text": text}


def run(steps, reason="final_answer", text="", cost=0.001):
    recs = [{"type": "run", "run_id": "r"}]
    for i, pairs in enumerate(steps, 1):
        recs.append({"type": "step", "n": i, "calls": [c for c, _ in pairs], "results": [r for _, r in pairs]})
    recs.append({"type": "stop", "reason": reason, "text": text, "cost_usd": cost, "input_tokens": 100,
                 "output_tokens": 20})
    return recs


GOOD = run([[call("lookup_employee", "a", text='{"name": "Dana Levi"}')],
            [call("check_policy", "b", text=json.dumps(POLICY))],
            [call("create_access_request", "c", text=json.dumps(CREATED))], []],
           text="Dana reports to Michal Ben-David. Route: needs_security. Filed AR-00001.")


def test_good_run():
    s = mine.score_trajectory(GOOD, GOLD, "t01")
    assert s["success"] and s["reasons"] == [] and s["task_id"] == "t01"
    assert (s["steps"], s["tool_calls"], s["errors"], s["redundant_calls"]) == (4, 3, 0, 0)
    assert s["efficiency"] == 1.0 and s["requests_created"] == 1 and not s["evidence_conflict"]
    assert s["cost_usd"] == 0.001 and s["tokens"] == 120 and s["stop_reason"] == "final_answer"


def test_wrong_request_field_and_missing_fact():
    bad = dict(CREATED, duration_days=90)
    recs = run([[call("lookup_employee", "a")], [call("check_policy", "b", text=json.dumps(POLICY))],
                [call("create_access_request", "c", text=json.dumps(bad))]], text="Filed. needs_security")
    s = mine.score_trajectory(recs, GOLD)
    assert not s["success"] and len(s["reasons"]) == 2  # duration_days, and the missing manager name


def test_no_request_and_limits():
    recs = run([[call("lookup_employee", "a")], [call("check_policy", "b", text=json.dumps(POLICY))]],
               reason="max_steps", text="Stopped. Michal Ben-David")
    s = mine.score_trajectory(recs, GOLD)
    assert not s["success"] and s["requests_created"] == 0 and len(s["reasons"]) == 2  # stop reason + no request


def test_redundancy_retry_and_local_tools():
    recs = run([[call("lookup_employee", "a", ok=False)], [call("lookup_employee", "a"), call("note", "n")],
                [call("lookup_employee", "a")], [call("lookup_employee", "a")]], text="x")
    s = mine.score_trajectory(recs, {"outcome": "no_request", "optimal_calls": 1})
    assert s["tool_calls"] == 4 and s["errors"] == 1
    assert s["redundant_calls"] == 2  # the retry after a failure is not redundant; the note is not counted
    assert s["efficiency"] == 0.25 and s["success"]


def test_efficiency_edge_cases():
    empty = run([[]], text="hello")
    assert mine.score_trajectory(empty, {"outcome": "no_request", "optimal_calls": 0})["efficiency"] == 1.0
    assert mine.score_trajectory(empty, {"outcome": "no_request", "optimal_calls": 2})["efficiency"] == 0.0
    assert mine.score_trajectory(empty, {"outcome": "no_request"})["efficiency"] is None


def test_forbidden_required_any_and_unexpected_request():
    recs = run([[call("create_access_request", "c", text=json.dumps(CREATED))]], reason="gave_up", text="Done")
    gold = {"outcome": "clarify", "forbidden_tools": ["create_access_request"], "required_tools": ["lookup_employee"],
            "answer_contains_any": ["which", "Shani Alon"]}
    s = mine.score_trajectory(recs, gold)
    assert not s["success"] and len(s["reasons"]) == 4  # forbidden, required, a request was created, any-of
    ok = run([[call("lookup_employee", "a", ok=False)]], reason="gave_up", text="Which SHANI ALON do you mean?")
    assert mine.score_trajectory(ok, {"outcome": "clarify", "answer_contains_any": ["shani alon"]})["success"]


def test_evidence_conflict():
    recs = run([[call("check_policy", "b", text=json.dumps(POLICY))]], text="This is AUTO_APPROVE per the doc.")
    s = mine.score_trajectory(recs, {"outcome": "no_request"})
    assert s["evidence_conflict"] and not s["success"]
    both = run([[call("check_policy", "b", text=json.dumps(POLICY))]],
               text="The doc says auto_approve, but check_policy says needs_security.")
    assert not mine.score_trajectory(both, {"outcome": "no_request"})["evidence_conflict"]
    none = run([[call("check_policy", "b", text=json.dumps(POLICY))]], text="It needs a review.")
    assert not mine.score_trajectory(none, {"outcome": "no_request"})["evidence_conflict"]


def test_summarize():
    a = mine.score_trajectory(GOOD, GOLD, "t01")
    b = mine.score_trajectory(run([[call("x", "a")], [call("x", "a")]], reason="repetition", cost=0.003),
                              {"outcome": "no_request", "optimal_calls": 1}, "t02")
    summ = mine.summarize_scores([a, b])
    assert summ["tasks"] == 2 and summ["successes"] == 1 and summ["success_rate"] == 0.5
    assert summ["mean_steps"] == 3.0 and summ["mean_tool_calls"] == 2.5
    assert summ["redundant_calls"] == 1 and summ["redundancy_rate"] == pytest.approx(0.2)
    assert summ["mean_efficiency"] == pytest.approx(0.75) and summ["errors"] == 0
    assert summ["cost_usd"] == pytest.approx(0.004) and summ["cost_per_success"] == pytest.approx(0.004)
    assert summ["stop_reasons"] == {"final_answer": 1, "repetition": 1} and summ["failed"] == ["t02"]
    assert summ["evidence_conflicts"] == 0
    zero = mine.summarize_scores([b])
    assert zero["cost_per_success"] is None
    assert mine.summarize_scores([])["success_rate"] == 0.0


def test_on_real_runs(tmp_path):
    tasks = {t["id"]: t for t in load_tasks(LAB / "data" / "tasks.jsonl")}
    for tid in ("t01", "t05", "t07", "t10"):
        reg = acme_registry(requests_db=tmp_path / f"{tid}.db")
        r = Agent(FakeLLM(AcmeHeuristic()), reg, confirm=lambda c: True).run(tasks[tid]["task"], task_id=tid)
        s = mine.score_trajectory(r.records, tasks[tid]["gold"], tid)
        assert s["success"], (tid, s["reasons"])
    reg = with_faults(acme_registry(requests_db=tmp_path / "m.db"), {"read_document": "stale"})
    r = Agent(FakeLLM(AcmeHeuristic()), reg).run(tasks["t11"]["task"])
    assert not mine.score_trajectory(r.records, tasks["t11"]["gold"])["success"]
