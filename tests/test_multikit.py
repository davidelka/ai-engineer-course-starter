"""Environment tests for multikit (lesson 18): every pattern offline, with fake models."""
import json
import tempfile
from pathlib import Path

import pytest

from agentkit import FakeLLM, load_tasks
from multikit import (CORRUPTIONS, CriticLoop, FanOut, HandoffError, Supervisor, aggregate_runs, build, citations,
                      corrupt_text, decide_route, domains_of, evidence_conflicts, make_handoff_brief, make_specialist,
                      merge_for_scoring, run_set, score_multi, score_research, split_by_domain)
from multikit.fake import CriticHeuristic, ResearchHeuristic, SpecialistHeuristic, SupervisorHeuristic, WriterHeuristic
from multikit.router import RouteDecision

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "18-multi-agent"
TASKS = {t["id"]: t for t in load_tasks(LAB / "data" / "tasks.jsonl")}


def run(pattern, tid, **kw):
    with tempfile.TemporaryDirectory() as d:
        return build(pattern, requests_db=Path(d) / "r.db", confirm=lambda c: True, **kw).run(
            TASKS[tid]["task"], task_id=tid)


def test_task_set_shape():
    assert len(TASKS) == 23 and sum(t.startswith("x") for t in TASKS) == 8
    for t in TASKS.values():
        assert "domains" in t["gold"] and t["gold"]["outcome"] in ("request_created", "no_request", "clarify")


def test_domains_split_cross_domain_tasks():
    assert all(domains_of(TASKS[f"t{i:02d}"]["task"]) == ["it_access"] for i in range(1, 16))
    for tid, t in TASKS.items():
        if tid.startswith("x"):
            assert domains_of(t["task"]) == t["gold"]["domains"], tid
    segs = split_by_domain(TASKS["x02"]["task"])
    assert segs[1].text.endswith("Do not file anything.")  # an unlabeled constraint sticks to its request


def test_decide_route_rules():
    d = RouteDecision(reason="r", routes=["oncall", "oncall", "hr"], confidence=0.7, clarifying_question=None)
    assert decide_route(d).targets == ["oncall"]
    assert decide_route(d, max_targets=3).targets == ["oncall", "hr"]
    assert decide_route(d, threshold=0.8).action == "clarify"


def test_router_routes_once_and_clarifies():
    r = run("router", "x03")
    assert [x.agent for x in r.runs] == ["router", "oncall"] and r.info["choice"]["targets"] == ["oncall"]
    assert not score_multi(r, TASKS["x03"]["gold"])["success"]  # half of a cross-domain task is lost
    assert score_multi(run("router2", "x03"), TASKS["x03"]["gold"])["success"]
    c = run("router", "x07")
    assert c.info["choice"]["action"] == "clarify" and len(c.runs) == 1


def test_supervisor_delegates_in_parallel_with_isolated_contexts():
    r = run("supervisor", "x08")
    assert r.runs[0].agent == "supervisor" and {x.agent for x in r.runs[1:]} == {"hr", "oncall", "it_access"}
    first = next(x for x in r.runs[0].records if x.get("type") == "step")
    assert len(first["calls"]) == 3  # all three delegations in one turn
    root = r.runs[0].run_id
    assert all(x.records[0]["parent_run_id"] == root for x in r.runs[1:])
    for w in r.runs[1:]:  # each worker saw only its brief, not the whole request
        head = w.records[0]
        assert "NetSuite" not in head["task"] or w.agent == "it_access"
    assert score_multi(r, TASKS["x08"]["gold"])["success"]
    seq = run("supervisor", "x08", parallel=False)
    assert sum(1 for x in seq.runs[0].records if x.get("type") == "step") == 4


def test_supervisor_verify_catches_a_corrupted_worker():
    bad = run("supervisor", "x06", worker_faults={"it_access": CORRUPTIONS["route"]})
    s = score_multi(bad, TASKS["x06"]["gold"])
    assert not s["success"] and s["evidence_conflict"]
    for v in ("llm", "code"):
        ok = run("supervisor", "x06", verify=v, worker_faults={"it_access": CORRUPTIONS["route"]}, fault_times=1)
        assert ok.info["delegations"]["it_access"] == 2 and score_multi(ok, TASKS["x06"]["gold"])["success"]
    assert run("supervisor", "x06", verify="code", worker_faults={"it_access": CORRUPTIONS["route"]}).info["warnings"]


def test_evidence_conflicts_and_corruption():
    ev = [{"tool": "check_policy", "data": {"route": "needs_security"}},
          {"tool": "get_oncall_for_service", "data": {"service": "billing-service", "team_lead": "Rina Sasson",
                                                      "rotation": "billing-oncall", "secondary": None}}]
    assert evidence_conflicts("route needs_security, lead Rina Sasson, billing-oncall", ev) == []
    probs = evidence_conflicts("auto_approve; Omer Haddad leads it; frontend-oncall", ev)
    assert len(probs) == 3
    assert corrupt_text("Rina Sasson and Omer Haddad", CORRUPTIONS["lead"]) == "Omer Haddad and Rina Sasson"


def test_hierarchical_team_lead():
    """A worker can itself be a supervisor (hierarchical teams): the tree keeps three levels."""
    def make_worker(d):
        if d == "oncall":
            return Supervisor(FakeLLM(SupervisorHeuristic()), lambda dd: make_specialist(dd, FakeLLM(SpecialistHeuristic(dd))),
                              workers=("oncall",), name="eng_lead")
        return make_specialist(d, FakeLLM(SpecialistHeuristic(d)))
    top = Supervisor(FakeLLM(SupervisorHeuristic()), make_worker, workers=("hr", "oncall"))
    r = top.run("Who is on call for connectors-hub? How many sick days does an employee accrue per month?")
    names = [x.agent for x in r.runs]
    assert names[0] == "supervisor" and "eng_lead" in names and "oncall" in names
    lead = next(x for x in r.runs if x.agent == "eng_lead")
    onc = next(x for x in r.runs if x.agent == "oncall")
    assert lead.records[0]["parent_run_id"] == r.runs[0].run_id and onc.records[0]["parent_run_id"] == lead.run_id
    assert "integrations-oncall" in r.text and "1.5" in r.text


H01 = ("Who is on call for flow-api? Dana Levi wants admin on aws-production for 3 days. Open the request, but do not "
       "file it before Friday.")


def _filed(r):
    return [c for x in r.records if x.get("type") == "step" for c in x["calls"] if c["name"] == "create_access_request"]


def test_handoff_chain_and_contract():
    from multikit import render_unchecked
    with tempfile.TemporaryDirectory() as d:
        ok = build("handoff", requests_db=Path(d) / "a.db", confirm=lambda c: True).run(H01)
        lossy = build("handoff", requests_db=Path(d) / "b.db", confirm=lambda c: True, lossy=True).run(H01)
        broken = build("handoff", requests_db=Path(d) / "c.db", confirm=lambda c: True, lossy=True,
                       brief=render_unchecked).run(H01)
    assert ok.info["chain"] == ["triage", "oncall", "it_access"] and not _filed(ok) and "core-api-oncall" in ok.text
    assert lossy.info["rejected"] and not _filed(lossy)
    assert _filed(broken)  # the lost constraint let the next agent file a request
    assert score_multi(run("handoff", "x05"), TASKS["x05"]["gold"])["success"]


def test_make_handoff_brief_reports_all_problems():
    with pytest.raises(HandoffError) as e:
        make_handoff_brief({"original_request": "x", "goal": "", "facts": [{"claim": "c", "source": ""}],
                            "actions_taken": [], "constraints": [], "open_questions": []}, H01, [{"id": "AR-9"}])
    assert len(e.value.problems) == 5


def test_fanout_research_with_citations():
    f = FanOut(FakeLLM(ResearchHeuristic("planner")), FakeLLM(ResearchHeuristic("worker")),
               FakeLLM(ResearchHeuristic("synth")))
    for line in (LAB / "data" / "research.jsonl").read_text().splitlines():
        q = json.loads(line)
        r = f.run(q["question"], task_id=q["id"])
        sc = score_research(r, q["gold"])
        assert sc["success"], (q["id"], sc, r.text)
        assert len([x for x in r.runs if x.role == "worker"]) == len(r.info["subquestions"])
    assert citations("a [hr-x-2026] b [sales-sla-2026] [hr-x-2026]") == ["hr-x-2026", "sales-sla-2026"]


def test_critic_loop_modes():
    case = json.loads((LAB / "data" / "critic_case.json").read_text())
    strict = CriticLoop(FakeLLM(WriterHeuristic()), FakeLLM(CriticHeuristic("strict"))).run(case["task"], case["facts"])
    assert strict.stop_reason == "passed" and len(strict.info["rounds"]) == 2 and "now have access" not in strict.text
    lenient = CriticLoop(FakeLLM(WriterHeuristic()), FakeLLM(CriticHeuristic("lenient"))).run(case["task"], case["facts"])
    assert lenient.stop_reason == "passed" and "now have access" in lenient.text  # a rubber stamp
    nit = CriticLoop(FakeLLM(WriterHeuristic()), FakeLLM(CriticHeuristic("nitpick")), max_rounds=3).run(
        case["task"], case["facts"])
    assert nit.stop_reason == "max_rounds" and len(nit.info["rounds"]) == 3


def test_aggregate_and_merge():
    r = run("supervisor", "x01")
    agg = aggregate_runs(r.records)
    assert set(agg["agents"]) == {"supervisor", "oncall", "it_access"}
    assert agg["total_cost_usd"] == pytest.approx(r.cost_usd) and 0 < agg["coordination_share"] < 1
    merged = merge_for_scoring(r)
    names = [c["name"] for x in merged if x.get("type") == "step" for c in x["calls"]]
    assert "create_access_request" in names and not any(n.startswith("delegate_to_") for n in names)


def test_compare_patterns_offline():
    tasks = list(TASKS.values())
    got = {p: sum(s["success"] for _, _, s in run_set(p, tasks)) for p in ("single", "router", "router2", "supervisor")}
    assert got == {"single": 23, "router": 16, "router2": 22, "supervisor": 23}
    rs = run_set("router", [TASKS["x01"]])
    assert rs[0][2]["blame"][0].startswith("router: did not route")
