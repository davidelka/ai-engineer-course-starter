"""agentkit (lesson 15): the agent loop, stop policy, planning, memory, trajectory, evaluation.

Offline only: FakeLLM (scripted / heuristic) and the in-process mockllm server.
"""

import json
import random
from pathlib import Path

import pytest

from agentkit import (AcmeHeuristic, Agent, Budget, FakeLLM, ScriptPolicy, StepRecord, clear_old_tool_results,
                      format_trajectory, load_tasks, load_trajectory, run_tasks, run_workflow, score_trajectory,
                      should_stop, split_runs, summarize_scores, to_spans, with_faults)
from agentkit.faults import parse_faults
from agentkit.fake import parse_task
from llmkit import LLM, RetryPolicy
from llmkit.types import Message, ToolCall, ToolResult
from mockllm import MockConfig, start_in_thread
from toolkit import acme_registry

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "labs" / "15-agent-loops" / "data" / "tasks.jsonl"
DANA = ("Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her "
        "manager, what does the policy say, and open the request (it goes to whatever track the policy requires).")


@pytest.fixture
def reg(tmp_path):
    return acme_registry(requests_db=tmp_path / "requests.db")


def fake(**kw):
    return FakeLLM(AcmeHeuristic(**kw))


def step(n, calls=(), fps=(), hashes=(), errors=0, **kw):
    return StepRecord(n, list(calls), list(fps), list(hashes), errors, **kw)


# ---------------------------------------------------------------- stop policy
def test_policy_order_and_reasons():
    b = Budget(max_steps=5)
    assert not should_stop([], b).stop
    assert should_stop([step(1, final=True)], b).reason == "final_answer"
    assert should_stop([step(1, gave_up=True)], b).reason == "gave_up"
    hist = [step(i, ["a"], [f"f{i}"], [f"h{i}"]) for i in range(1, 6)]
    assert should_stop(hist, b).reason == "max_steps"
    # a final answer on the last allowed step is still a success
    assert should_stop(hist[:4] + [step(5, final=True)], b).reason == "final_answer"


def test_policy_budgets():
    h = [step(1, ["a"], ["f1"], ["h1"], tokens=600, cost_usd=0.002, elapsed_s=2.0)]
    assert should_stop(h, Budget(max_tokens=500)).reason == "budget_tokens"
    assert should_stop(h, Budget(max_cost_usd=0.002)).reason == "budget_cost"
    assert should_stop(h, Budget(max_cost_usd=0.0035)).reason == "budget_cost"  # the next step would overspend
    assert not should_stop(h, Budget(max_cost_usd=0.0041)).stop
    assert should_stop(h, Budget(max_seconds=1.5)).reason == "budget_time"


def test_policy_repetition_errors_and_no_progress():
    rep = [step(i, ["lookup"], ["same"], ["h"]) for i in range(1, 4)]
    d = should_stop(rep, Budget())
    assert d.reason == "repetition" and "3 times" in d.detail
    errs = [step(i, ["a"], [f"f{i}"], [None], errors=1) for i in range(1, 4)]
    assert should_stop(errs, Budget()).reason == "tool_errors"
    assert should_stop(errs, Budget(max_consecutive_errors=0)).reason == "no_progress"
    para = [step(1, ["l"], ["f1"], ["h1"])] + [step(i, ["l"], [f"f{i}"], ["h1"]) for i in range(2, 5)]
    assert should_stop(para, Budget()).reason == "no_progress"
    assert not should_stop(para[:3], Budget()).stop  # only 2 steps without progress so far
    assert not should_stop(para, Budget(no_progress_steps=0)).stop


# ---------------------------------------------------------------- the loop
def test_react_run_files_request_with_confirmation(reg, tmp_path):
    seen = []
    log = tmp_path / "t.jsonl"
    res = Agent(fake(), reg, confirm=lambda c: seen.append(c.name) or True, log_path=str(log)).run(DANA, task_id="t01")
    assert res.stop_reason == "final_answer" and res.steps == 4
    assert res.tool_names == ["lookup_employee", "check_policy", "create_access_request"]
    assert seen == ["create_access_request"]
    assert "Michal Ben-David" in res.text and "needs_security" in res.text and "2026-11-04" in res.text
    assert res.estimated_cost and res.cost_usd > 0
    recs = load_trajectory(log)
    assert [r["type"] for r in recs][0] == "run" and recs[-1]["type"] == "stop"
    assert any(r["type"] == "confirm" and r["approved"] for r in recs)
    assert res.side_effects() and json.loads(res.side_effects()[0]["text"])["route"] == "needs_security"
    assert "STOP final_answer" in format_trajectory(recs)


def test_side_effects_never_run_without_a_human(reg):
    res = Agent(fake(), reg).run(DANA)
    assert res.stop_reason == "final_answer" and not res.side_effects()
    assert any("NOT executed" in r.text for r in res.results)
    res = Agent(fake(), reg, confirm=lambda c: False).run(DANA)
    assert not res.side_effects() and any("DECLINED" in r.text for r in res.results)


def test_loops_are_stopped(reg):
    r = Agent(fake(loop="repeat"), reg).run(DANA)
    assert r.stop_reason == "repetition" and r.steps == 3
    r = Agent(fake(loop="paraphrase"), reg).run(DANA)
    assert r.stop_reason == "no_progress" and len(set(r.tool_names)) == 1
    assert len({json.dumps(c.arguments) for c in r.calls}) > 1  # different arguments: repetition alone misses it


def test_tool_errors_recovery_and_give_up(tmp_path):
    reg = with_faults(acme_registry(requests_db=tmp_path / "a.db"), {"lookup_employee": "error:1"})
    r = Agent(fake(), reg, confirm=lambda c: True).run(DANA)
    assert r.stop_reason == "final_answer" and r.errors == 1 and r.side_effects()
    reg = with_faults(acme_registry(requests_db=tmp_path / "b.db"), {"lookup_employee": "error"})
    r = Agent(fake(), reg).run(DANA)
    assert r.stop_reason == "gave_up" and "keeps failing" in r.text
    r = Agent(fake(stubborn=True), reg, budget=Budget(repeat_limit=10)).run(DANA)
    assert r.stop_reason == "tool_errors"
    assert parse_faults(["lookup_employee=error:1"]) == {"lookup_employee": "error:1"}
    with pytest.raises(ValueError):
        with_faults(reg, {"nope": "error"})


def test_budget_stop_and_summary(reg):
    r = Agent(fake(), reg, budget=Budget(max_cost_usd=0.0004)).run(DANA)
    assert r.stop_reason == "budget_cost" and r.steps == 1 and r.text.startswith("Stopped")
    r2 = Agent(fake(), reg, budget=Budget(max_cost_usd=0.0004), summarize_on_stop=True).run(DANA)
    assert r2.stop_reason == "budget_cost" and r2.cost_usd > r.cost_usd and not r2.text.startswith("Stopped")
    r3 = Agent(fake(), reg, budget=Budget(max_steps=2)).run(DANA)
    assert r3.stop_reason == "max_steps" and r3.messages[-1].tool_results  # no dangling tool calls


def test_scripted_policy_and_give_up_tool(reg):
    script = [{"text": "Looking up.", "calls": [{"name": "lookup_employee", "arguments": {"employee": "E016"}}]},
              {"calls": [{"name": "give_up", "arguments": {"reason": "Test reason.", "missing": "nothing"}}]}]
    r = Agent(FakeLLM(ScriptPolicy(script)), reg).run("anything")
    assert r.stop_reason == "gave_up" and "Test reason." in r.text and r.steps == 2
    assert r.records[1]["thought"] == "Looking up."


def test_plan_mode_and_replan(tmp_path):
    reg = acme_registry(requests_db=tmp_path / "p.db")
    r = Agent(fake(), reg, confirm=lambda c: True, mode="plan").run(DANA)
    assert r.plan and r.plan["steps"][0]["tool"] == "lookup_employee"
    assert r.steps == 3 and len(r.records[2]["calls"]) == 2  # the plan batches independent reads
    reg = with_faults(acme_registry(requests_db=tmp_path / "q.db"), {"lookup_employee": "error:1"})
    r = Agent(fake(), reg, confirm=lambda c: True, mode="plan").run(DANA)
    assert r.replans == 1 and r.stop_reason == "final_answer"
    assert sum(1 for x in r.records if x["type"] == "plan") == 2


def test_memory_trimming_and_notes(reg):
    msgs = [Message("user", "q"),
            Message("assistant", [ToolCall("a", "lookup_employee", {"employee": "E016"})]),
            Message.with_tool_results([ToolResult("a", "x" * 50, name="lookup_employee")]),
            Message("assistant", [ToolCall("b", "check_policy", {})]),
            Message.with_tool_results([ToolResult("b", "y" * 50, name="check_policy", is_error=True)])]
    out, n = clear_old_tool_results(msgs, keep=1)
    assert n == 1 and out[2].tool_results[0].content.startswith("[cleared:") and out[2].tool_results[0].call_id == "a"
    assert msgs[2].tool_results[0].content == "x" * 50  # input untouched
    assert out[4] is msgs[4]
    out2, n2 = clear_old_tool_results(out, keep=0)
    assert n2 == 1 and out2[4].tool_results[0].is_error
    # end to end: trimming without notes makes the agent re-fetch; notes fix it
    r = Agent(fake(), reg, confirm=lambda c: True, keep_tool_results=1).run(DANA)
    assert r.stop_reason == "repetition"
    r = Agent(fake(), reg, confirm=lambda c: True, keep_tool_results=1, scratchpad=True).run(DANA)
    assert r.stop_reason == "final_answer" and "note" in r.tool_names and "Michal Ben-David" in r.text
    assert any(x["type"] == "trim" for x in r.records)


def test_spans_for_obskit(reg):
    r = Agent(fake(), reg, confirm=lambda c: True).run(DANA)
    spans = to_spans(r.records)
    kinds = [s["attributes"]["obskit.span.type"] for s in spans]
    assert kinds[0] == "agent" and kinds.count("llm") == 4 and kinds.count("tool") == 3
    assert all(s["trace_id"] == spans[0]["trace_id"] for s in spans)
    from obskit.analyze import summarize
    assert summarize(spans)  # the lesson-22 analyzer reads them


def test_obskit_live_spans(reg):
    from obskit import setup_tracing
    tr = setup_tracing("t15", memory=True)
    try:
        Agent(fake(), reg, confirm=lambda c: True, trace=True).run(DANA)
        names = [s["name"] for s in tr.memory.spans]
    finally:
        tr.shutdown()
    assert "invoke_agent company_brain" in names and names.count("execute_tool lookup_employee") == 1


# ---------------------------------------------------------------- mockllm (real wire shapes)
@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
def test_mockllm_script_and_loop(tmp_path, provider):
    srv, url = start_in_thread(MockConfig(ttft=0, tps=0, seed=1,
                                          tool_script=str(ROOT / "labs/15-agent-loops/data/mock_script.json")))
    try:
        llm = LLM(f"{provider}:mock-model", api_key="t", base_url=url,
                  retry=RetryPolicy(sleep=lambda s: None, rng=random.Random(0)))
        r = Agent(llm, acme_registry(requests_db=tmp_path / "m.db"), confirm=lambda c: True).run(DANA)
        assert r.stop_reason == "final_answer" and r.side_effects() and not r.estimated_cost
        srv.state.cfg.tool_fault, srv.state.cfg.tool_fault_rate = "loop", 1.0
        r = Agent(llm, acme_registry(requests_db=tmp_path / "n.db")).run(DANA)
        assert r.stop_reason == "repetition"
    finally:
        srv.shutdown()


# ---------------------------------------------------------------- evaluation and the task set
def test_task_set_is_well_formed():
    tasks = load_tasks(TASKS)
    assert 12 <= len(tasks) <= 15 and len({t["id"] for t in tasks}) == len(tasks)
    for t in tasks:
        g = t["gold"]
        assert g["outcome"] in ("request_created", "no_request", "clarify")
        assert (g["outcome"] == "request_created") == ("request" in g)
        assert "optimal_calls" in g


@pytest.mark.parametrize("mode", ["react", "plan"])
def test_heuristic_solves_task_set(mode):
    rows = run_tasks(lambda db: Agent(fake(), acme_registry(requests_db=db), confirm=lambda c: True, mode=mode),
                     load_tasks(TASKS))
    summ = summarize_scores([s for *_, s in rows])
    assert summ["success_rate"] == 1.0, summ["failed"]
    assert summ["redundant_calls"] == 0


def test_scoring_catches_failures(reg):
    task = load_tasks(TASKS)[0]
    r = Agent(fake(), reg).run(task["task"])  # no confirmation: no request filed
    s = score_trajectory(r.records, task["gold"], "t01")
    assert not s["success"] and any("expected 1 request" in x for x in s["reasons"])
    r = Agent(fake(loop="repeat"), reg).run(task["task"])
    s = score_trajectory(r.records, task["gold"], "t01")
    assert s["stop_reason"] == "repetition" and s["redundant_calls"] == 2 and not s["success"]
    reg2 = with_faults(reg, {"read_document": "misleading"})
    t11 = next(t for t in load_tasks(TASKS) if t["id"] == "t11")
    r = Agent(fake(), reg2).run(t11["task"])
    s = score_trajectory(r.records, t11["gold"], "t11")
    assert not s["success"] and any("2 business days" in x for x in s["reasons"])


def test_evidence_conflict_with_naive_docs(reg):
    task = ("Dana Levi wants admin on aws-production for 3 days. What does the access policy document say, and "
            "which route does check_policy give? Do not file anything.")
    reg2 = with_faults(reg, {"read_document": "misleading"})
    gold = {"outcome": "no_request", "answer_contains": ["needs_security"]}
    s = score_trajectory(Agent(fake(naive_docs=True), reg2).run(task).records, gold)
    assert s["evidence_conflict"] and not s["success"]
    s = score_trajectory(Agent(fake(), reg2).run(task).records, gold)
    assert not s["evidence_conflict"] and s["success"]


def test_workflow_same_format_and_limits(tmp_path):
    tasks = {t["id"]: t for t in load_tasks(TASKS)}
    reg = acme_registry(requests_db=tmp_path / "w.db")
    r = run_workflow(tasks["t01"]["task"], reg, confirm=lambda c: True, task_id="t01")
    s = score_trajectory(r.records, tasks["t01"]["gold"], "t01")
    assert s["success"] and r.cost_usd == 0 and s["tool_calls"] == 3
    r = run_workflow(tasks["t07"]["task"], reg, task_id="t07")
    assert r.stop_reason == "unsupported" and not score_trajectory(r.records, tasks["t07"]["gold"])["success"]
    runs = split_runs(r.records)
    assert len(runs) == 1


def test_parse_task():
    s = parse_task(DANA)
    assert (s.employee, s.system, s.level, s.duration, s.wants_request) == ("Dana Levi", "aws-production", "admin", 3, True)
    s = parse_task("Ofer Levi wants to connect a third-party OAuth app to Google Workspace. Do not file anything yet.")
    assert s.external and not s.wants_request and s.system == "google-workspace"
