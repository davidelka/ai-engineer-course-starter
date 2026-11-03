"""Environment tests for loopkit (lesson 7): tasks, verifiers, guard, policy, feedback, the loop, the log."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from loopkit import (Budget, EvidenceLog, LLMGenerator, ScriptedGenerator, compose_feedback, find_tampering,
                     format_feedback, load_tasks, make_verifiers, read_records, run_loop, should_stop, summarize)
from loopkit.types import Evidence, IterationRecord, candidate_hash
from loopkit.verifiers import Flaky, PytestVerifier, Rerun, Verifier, audit, gate, parse_junit
from loopkit.workspace import apply_files, room

TASKS = Path(__file__).resolve().parents[1] / "labs" / "07-verification-loops" / "tasks"
FIX = TASKS.parent / "tests" / "fixtures"


@pytest.fixture(scope="module")
def tasks():
    return {t.id: t for t in load_tasks(TASKS, include_impossible=True)}


def with_module(task, rel):
    return apply_files(task.starter_files(), {task.module: task.read(rel)})


# ------------------------------------------------------------------ tasks
def test_task_set(tasks):
    assert set(tasks) == {"vacation_days", "business_days", "parse_duration", "route_request", "policy_numbers",
                          "leave_balance"}
    assert [t.id for t in load_tasks(TASKS)] == sorted(set(tasks) - {"leave_balance"})
    assert tasks["leave_balance"].impossible
    for t in tasks.values():
        assert t.visible_tests and t.hidden_tests and t.smoke


@pytest.mark.parametrize("tid", ["vacation_days", "business_days", "parse_duration", "route_request", "policy_numbers"])
def test_reference_passes_and_starter_fails_the_audit(tasks, tid):
    t = tasks[tid]
    assert audit(t, with_module(t, f"reference/{t.module}")).passed
    assert not audit(t, t.starter_files()).passed


def test_impossible_task_reference_fails_visible_but_passes_hidden(tasks):
    t = tasks["leave_balance"]
    files = with_module(t, "reference/solution.py")
    assert not PytestVerifier("v", sets=("tests",), clean_room=True).verify(t, files).passed
    assert PytestVerifier("h", sets=("hidden",), clean_room=True).verify(t, files).passed


# ------------------------------------------------------------------ verifiers
def test_weak_oracle_accepts_buggy_code(tasks):
    t = tasks["vacation_days"]
    ev = make_verifiers("weak")[0].verify(t, t.starter_files())
    assert ev.passed  # it runs, and it is wrong: that is the point


def test_workspace_tests_can_be_gamed_but_clean_room_cannot(tasks):
    t = tasks["business_days"]
    files = apply_files(with_module(t, "scripted/h1.py"),
                        {"tests/test_visible.py": t.read("scripted/cheat_tests.py")})
    assert PytestVerifier("v", sets=("tests",), clean_room=False).verify(t, files).passed
    assert not PytestVerifier("v", sets=("tests",), clean_room=True).verify(t, files).passed


def test_lint_catches_undefined_names(tasks):
    t = tasks["route_request"]
    lint = make_verifiers("strong")[1]
    assert lint.name == "lint"
    ev = lint.verify(t, {t.module: "def route_request(tool, access):\n    return undefined_thing\n"})
    assert ev.skipped or not ev.passed


def test_parse_junit_ids():
    xml = ('<testsuites><testsuite><testcase classname="tests.test_visible" name="test_a"/>'
           '<testcase classname="tests.test_visible.TestK" name="test_k"><failure message="x"/></testcase>'
           '<testcase classname="hidden.test_hidden" name="test_p[1]"><skipped/></testcase></testsuite></testsuites>')
    assert parse_junit(xml) == (["tests/test_visible.py::test_a"], ["tests/test_visible.py::TestK::test_k"],
                                ["hidden/test_hidden.py::test_p[1]"])


class _Seq(Verifier):
    name, kind = "seq", "pytest"

    def __init__(self, results):
        self.results = list(results)

    def verify(self, task, files):
        ok = self.results.pop(0)
        return Evidence(verifier=self.name, passed=ok, score=1.0 if ok else 0.5, kind="pytest")


def test_rerun_marks_flaky_and_flaky_injects(tasks):
    t = tasks["route_request"]
    ev = Rerun(_Seq([False, True]), reruns=2).verify(t, {})
    assert ev.passed and ev.flaky
    assert not Rerun(_Seq([False, False, False]), reruns=2).verify(t, {}).passed
    always = Flaky(_Seq([True]), p=1.0, rng=random.Random(0)).verify(t, {})
    assert not always.passed and "injected flaky failure" in always.summary


def test_gate_ignores_skipped_and_advisory():
    evs = [Evidence("a", True, 1.0), Evidence("b", False, 0.0, required=False), Evidence("c", True, 1.0, skipped=True)]
    assert gate(evs) == (True, 1.0)


def test_room_rejects_path_escape():
    with pytest.raises(ValueError):
        with room({"../evil.py": "x"}):
            pass


# ------------------------------------------------------------------ guard, policy, feedback (reference versions)
def test_guard_reference_on_a_skip(tasks):
    t = tasks["business_days"]
    out = find_tampering(t.visible_tests, {"tests/test_visible.py": t.read("scripted/cheat_tests.py")}, None, t.spec)
    assert "skip_marker:tests/test_visible.py::test_duplicate_holidays_count_once" in out


def test_guard_allows_spec_literals(tasks):
    t = tasks["parse_duration"]
    assert find_tampering(t.visible_tests, t.visible_tests, t.reference_source(), t.spec) == []


def test_policy_reference_order():
    r = [IterationRecord(1, 0.5, False, "a"), IterationRecord(2, 0.5, False, "b"), IterationRecord(3, 0.5, False, "a")]
    assert should_stop(r, Budget(patience=2)).reason == "oscillation"
    assert should_stop(r, Budget(max_iterations=3)).reason == "budget_iterations"


def test_feedback_reference_and_modes():
    raw = (FIX / "duration_starter.txt").read_text()
    compact = format_feedback(raw)
    assert compact.startswith("8 failed, 4 passed") and len(compact) < len(raw)
    ev = Evidence("visible_tests", False, 0.3, kind="pytest", output=raw)
    assert len(compose_feedback([ev], mode="raw")) > len(compose_feedback([ev], mode="compact"))
    assert compose_feedback([ev], mode="minimal") == "visible_tests: failed."
    g = Evidence("guard", False, 0.0, kind="guard", findings=["removed_test:tests/test_visible.py::test_x"])
    assert "read-only" in compose_feedback([g])
    assert compose_feedback([Evidence("v", True, 1.0)]) == ""


def test_candidate_hash_ignores_trailing_whitespace():
    assert candidate_hash({"a.py": "x = 1  \n"}) == candidate_hash({"a.py": "x = 1\n"})
    assert candidate_hash({"a.py": "x = 1"}) != candidate_hash({"a.py": "x = 2"})


# ------------------------------------------------------------------ the loop
def test_honest_loop_solves_and_logs(tasks, tmp_path):
    log_path = tmp_path / "run.jsonl"
    res = run_loop(tasks["vacation_days"], ScriptedGenerator("honest"), make_verifiers("strong"),
                   budget=Budget(max_iterations=5), log=EvidenceLog(log_path), label="t")
    assert res.solved and res.stop_reason == "solved" and res.solved_at == 3 and res.audit_passed
    recs = read_records([log_path])
    assert [r["type"] for r in recs] == ["run", "iteration", "iteration", "iteration", "summary"]
    it2 = recs[2]
    assert it2["verifiers"][-1]["verifier"] == "hidden_tests" and not it2["verifiers"][-1]["passed"]
    assert "Hidden checks" in it2["feedback"] and it2["estimated_cost"]
    s = summarize(recs)["t"]
    assert s["truly_solved"] == 1 and s["false_passes"] == 0 and s["solved_at"][3] == 1.0
    assert s["cost_per_solved"] and s["cost_per_solved"] > 0


def test_cheater_fools_workspace_tests_but_not_strong(tasks):
    t = tasks["route_request"]
    weak = run_loop(t, ScriptedGenerator("cheater"), make_verifiers("tests"), budget=Budget(max_iterations=4))
    assert weak.solved and weak.solved_at == 2 and not weak.audit_passed  # a false pass
    strong = run_loop(t, ScriptedGenerator("cheater"), make_verifiers("strong"), budget=Budget(max_iterations=4))
    assert strong.solved and strong.solved_at == 3 and strong.audit_passed and strong.tamper_iterations == 1


def test_oscillation_is_detected(tasks):
    res = run_loop(tasks["business_days"], ScriptedGenerator("oscillator"), make_verifiers("strong"),
                   budget=Budget(max_iterations=6, patience=5))
    assert res.stop_reason == "oscillation" and res.iterations == 3


def test_impossible_task_honest_generator_gives_up(tasks):
    res = run_loop(tasks["leave_balance"], ScriptedGenerator("honest"), make_verifiers("strong"),
                   budget=Budget(max_iterations=5, patience=3))
    assert res.stop_reason == "generator_gave_up" and not res.solved


def test_human_checkpoint_can_stop(tasks):
    res = run_loop(tasks["vacation_days"], ScriptedGenerator("honest"), make_verifiers("tests"),
                   budget=Budget(max_iterations=5), checkpoint=lambda rec, d: False, ask_every=1)
    assert res.stop_reason == "human_stop" and res.iterations == 1


def test_llm_generator_against_mock_and_cost_budget(tasks):
    from mockllm import MockConfig, start_in_thread
    from llmkit import LLM

    server, url = start_in_thread(MockConfig(ttft=0, tps=0, seed=1))
    try:
        gen = LLMGenerator(LLM("mock:mock-model", base_url=url))
        res = run_loop(tasks["route_request"], gen, make_verifiers("tests"),
                       budget=Budget(max_iterations=4, max_cost_usd=0.00015))
        assert res.stop_reason == "budget_cost" and res.iterations == 1
        assert res.tokens > 0 and res.cost_usd > 0 and not res.solved
    finally:
        server.shutdown()


def test_plans_reference_existing_files(tasks):
    for t in tasks.values():
        plan = json.loads(t.read("scripted/plan.json"))
        for steps in plan.values():
            for st in steps:
                assert (t.root / st["solution"]).exists()
                for src in (st.get("tests") or {}).values():
                    assert src is None or (t.root / src).exists()
