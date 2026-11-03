"""Exercise 6: per-agent cost and time attribution over multi-agent trajectories."""
import pytest

import mine


def run(rid, agent, role, t0, t1, tin, tout, cost, el, calls=()):
    recs = [{"run_id": rid, "type": "run", "agent": agent, "ts": t0}]
    if role is not None:
        recs[0]["role"] = role
    recs.append({"run_id": rid, "type": "step", "n": 1, "ts": (t0 + t1) / 2,
                 "calls": [{"name": c} for c in calls], "results": [{} for _ in calls]})
    recs.append({"run_id": rid, "type": "stop", "ts": t1, "input_tokens": tin, "output_tokens": tout,
                 "cost_usd": cost, "elapsed_s": el})
    return recs


RECS = (run("s", "supervisor", "coordinator", 0, 3000, 1000, 100, 0.002, 3.0, ["delegate_to_hr", "delegate_to_oncall"])
        + run("h", "hr", "worker", 500, 2500, 2000, 200, 0.004, 2.0, ["search_hr_policies", "note", "read_document"])
        + run("o", "oncall", "worker", 500, 1500, 500, 50, 0.002, 1.0, ["get_oncall_for_service"]))


def test_per_agent_sums():
    a = mine.aggregate_runs(RECS)
    hr = a["agents"]["hr"]
    assert (hr["role"], hr["runs"], hr["steps"], hr["tool_calls"]) == ("worker", 1, 1, 2)
    assert (hr["input_tokens"], hr["output_tokens"], hr["tokens"]) == (2000, 200, 2200)
    assert hr["cost_share"] == pytest.approx(0.5)
    assert a["agents"]["supervisor"]["tool_calls"] == 2


def test_totals_and_coordination():
    a = mine.aggregate_runs(RECS)
    assert a["runs"] == 3 and a["total_tokens"] == 3850
    assert a["total_cost_usd"] == pytest.approx(0.008)
    assert a["coordination_cost_usd"] == pytest.approx(0.002) and a["coordination_share"] == pytest.approx(0.25)


def test_wall_time_and_parallelism():
    a = mine.aggregate_runs(RECS)
    assert a["wall_s"] == pytest.approx(3.0) and a["agent_s"] == pytest.approx(6.0)
    assert a["parallelism"] == pytest.approx(2.0)


def test_same_agent_many_runs_and_missing_fields():
    recs = run("a", "it_access", None, 0, 1000, 10, 1, 0.0, 1.0) + run("b", "it_access", "worker", 1000, 2000, 20, 2, 0.0, 1.0)
    recs.append({"run_id": "c", "type": "run", "agent": "router", "role": "coordinator"})  # no stop, no ts
    a = mine.aggregate_runs(recs)
    assert a["agents"]["it_access"]["runs"] == 2 and a["agents"]["it_access"]["tokens"] == 33
    assert a["agents"]["it_access"]["role"] == "worker" and a["agents"]["it_access"]["cost_share"] == 0.0
    assert a["agents"]["router"]["tokens"] == 0 and a["coordination_share"] == 0.0 and a["runs"] == 3


def test_empty():
    a = mine.aggregate_runs([])
    assert a["runs"] == 0 and a["wall_s"] == 0.0 and a["parallelism"] == 1.0


def test_matches_a_real_supervisor_run():
    from multikit import aggregate_runs, build
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        r = build("supervisor", requests_db=Path(d) / "r.db", confirm=lambda c: True).run(
            "Who is on call for connectors-hub? How many sick days does an employee accrue per month?", task_id="t")
    mine_a, ref = mine.aggregate_runs(r.records), aggregate_runs(r.records)
    assert set(mine_a["agents"]) == {"supervisor", "oncall", "hr"}
    for k in ("runs", "total_tokens", "coordination_share"):
        assert mine_a[k] == pytest.approx(ref[k])
