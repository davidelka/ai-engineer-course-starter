"""Exercise 3: the stop policy (pure function), then the same policy inside a real agent run."""
import pytest

import mine
from agentkit import AcmeHeuristic, Agent, FakeLLM
from agentkit.types import Budget, StepRecord
from toolkit import acme_registry

DANA = ("Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her "
        "manager, what does the policy say, and open the request (it goes to whatever track the policy requires).")


def s(n, calls=(), fps=(), hashes=(), errors=0, **kw):
    return StepRecord(n, list(calls), list(fps), list(hashes), errors, **kw)


def ok(i, h=None):
    return s(i, ["t"], [f"f{i}"], [h or f"h{i}"])


def test_empty_continues():
    d = mine.should_stop([], Budget())
    assert d.stop is False and d.reason == "continue"


def test_final_and_give_up():
    assert mine.should_stop([ok(1), s(2, final=True)], Budget()).reason == "final_answer"
    assert mine.should_stop([s(1, gave_up=True)], Budget()).reason == "gave_up"


def test_final_beats_limits():
    hist = [ok(i) for i in range(1, 3)] + [s(3, final=True, cost_usd=1.0)]
    assert mine.should_stop(hist, Budget(max_steps=3, max_cost_usd=0.01)).reason == "final_answer"


def test_max_steps():
    d = mine.should_stop([ok(i) for i in range(1, 4)], Budget(max_steps=3))
    assert d.stop and d.reason == "max_steps" and d.detail
    assert not mine.should_stop([ok(i) for i in range(1, 3)], Budget(max_steps=3)).stop


def test_tokens_cost_time():
    h = [s(1, ["t"], ["a"], ["x"], tokens=300, cost_usd=0.001, elapsed_s=1.0),
         s(2, ["t"], ["b"], ["y"], tokens=300, cost_usd=0.001, elapsed_s=1.0)]
    assert mine.should_stop(h, Budget(max_tokens=600)).reason == "budget_tokens"
    assert not mine.should_stop(h, Budget(max_tokens=601)).stop
    assert mine.should_stop(h, Budget(max_cost_usd=0.002)).reason == "budget_cost"
    assert mine.should_stop(h, Budget(max_cost_usd=0.0025)).reason == "budget_cost"  # lookahead
    assert not mine.should_stop(h, Budget(max_cost_usd=0.0031)).stop
    assert mine.should_stop(h, Budget(max_seconds=2.0)).reason == "budget_time"
    assert not mine.should_stop(h, Budget(max_seconds=2.5)).stop


def test_order_when_several_apply():
    h = [s(i, ["t"], ["same"], ["x"], tokens=1000, cost_usd=1.0) for i in range(1, 4)]
    assert mine.should_stop(h, Budget(max_steps=3, max_tokens=10, max_cost_usd=0.1)).reason == "max_steps"
    assert mine.should_stop(h, Budget(max_tokens=10, max_cost_usd=0.1)).reason == "budget_tokens"
    assert mine.should_stop(h, Budget(max_cost_usd=0.1)).reason == "budget_cost"
    assert mine.should_stop(h, Budget()).reason == "repetition"


def test_repetition_counts_whole_history():
    h = [s(1, ["a"], ["X"], ["h1"]), ok(2), s(3, ["a", "b"], ["X", "Y"], ["h1", "h3"])]
    assert not mine.should_stop(h, Budget()).stop  # X twice
    h.append(s(4, ["a"], ["X"], ["h1"]))
    d = mine.should_stop(h, Budget())
    assert d.reason == "repetition" and d.detail
    assert not mine.should_stop(h, Budget(repeat_limit=4, no_progress_steps=0)).stop


def test_repetition_only_looks_at_last_step():
    h = [s(i, ["a"], ["X"], [f"h{i}"]) for i in range(1, 4)] + [ok(4)]
    assert not mine.should_stop(h, Budget()).stop


def test_tool_errors():
    errs = [s(i, ["a"], [f"f{i}"], [None], errors=1) for i in range(1, 4)]
    assert mine.should_stop(errs, Budget()).reason == "tool_errors"
    mixed = errs[:2] + [s(3, ["a", "b"], ["f3", "g3"], [None, "h"], errors=1)]
    assert mine.should_stop(mixed, Budget()).reason != "tool_errors"
    assert mine.should_stop(errs, Budget(max_consecutive_errors=0, no_progress_steps=0)).stop is False


def test_no_progress():
    h = [ok(1, "A"), ok(2, "A"), ok(3, "A")]
    assert not mine.should_stop(h, Budget()).stop  # 2 steps without progress
    h.append(ok(4, "A"))
    assert mine.should_stop(h, Budget()).reason == "no_progress"
    h2 = [ok(1, "A"), ok(2, "A"), ok(3, "A"), ok(4, "B")]
    assert not mine.should_stop(h2, Budget()).stop
    assert not mine.should_stop(h, Budget(no_progress_steps=0)).stop
    # a hash seen long ago is not new
    h3 = [ok(1, "A"), ok(2, "B"), ok(3, "A"), ok(4, "B"), ok(5, "A")]
    assert mine.should_stop(h3, Budget()).reason == "no_progress"


def test_inside_an_agent(tmp_path):
    reg = acme_registry(requests_db=tmp_path / "r.db")
    r = Agent(FakeLLM(AcmeHeuristic(loop="repeat")), reg, policy=mine.should_stop).run(DANA)
    assert r.stop_reason == "repetition" and r.steps == 3
    r = Agent(FakeLLM(AcmeHeuristic(loop="paraphrase")), reg, policy=mine.should_stop).run(DANA)
    assert r.stop_reason == "no_progress"
    r = Agent(FakeLLM(AcmeHeuristic()), reg, policy=mine.should_stop, confirm=lambda c: True).run(DANA)
    assert r.stop_reason == "final_answer" and r.side_effects()


def test_notes_alone_are_not_progress(tmp_path):
    # the agent records a note's result hash as None (its text changes on every call but teaches nothing),
    # so a model that only writes notes must be stopped by YOUR rule 10, not run to max_steps
    from agentkit import ScriptPolicy
    reg = acme_registry(requests_db=tmp_path / "r.db")
    turns = [{"calls": [{"name": "note", "arguments": {"text": f"thinking, round {i}"}}]} for i in range(10)]
    r = Agent(FakeLLM(ScriptPolicy(turns)), reg, policy=mine.should_stop, scratchpad=True).run(DANA)
    assert r.stop_reason == "no_progress" and r.steps == 3


@pytest.mark.parametrize("budget,reason", [(Budget(max_steps=2), "max_steps"),
                                           (Budget(max_cost_usd=0.0004), "budget_cost"),
                                           (Budget(max_tokens=3000), "budget_tokens")])
def test_budgets_inside_an_agent(tmp_path, budget, reason):
    reg = acme_registry(requests_db=tmp_path / "r.db")
    r = Agent(FakeLLM(AcmeHeuristic()), reg, policy=mine.should_stop, budget=budget).run(DANA)
    assert r.stop_reason == reason
