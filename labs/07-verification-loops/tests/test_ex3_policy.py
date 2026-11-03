"""Exercise 3: the stop policy. Every rule, and the order between the rules."""

from loopkit.types import Budget, IterationRecord, StopDecision
from mine import should_stop


def rec(i, score=0.5, solved=False, h=None, tokens=1000, cost=0.001, elapsed=1.0, tampered=False):
    return IterationRecord(iteration=i, score=score, solved=solved, candidate_hash=h or f"h{i}",
                           tokens=tokens, cost_usd=cost, elapsed_s=elapsed, tampered=tampered)


def reason(history, **kw):
    d = should_stop(history, Budget(**kw))
    assert isinstance(d, StopDecision)
    return d.reason if d.stop else "continue"


def test_empty_history_continues():
    d = should_stop([], Budget())
    assert d.stop is False and d.reason == "continue"


def test_improving_run_continues():
    assert reason([rec(1, 0.3), rec(2, 0.6)]) == "continue"


def test_solved_stops():
    assert reason([rec(1, 0.4), rec(2, 1.0, solved=True)]) == "solved"


def test_solved_wins_over_budget():
    assert reason([rec(1), rec(2, 1.0, solved=True)], max_iterations=2) == "solved"


def test_tampered_solution_is_not_solved():
    # the guard flagged it: it does not count as solved, and one tamper is below max_tamper=2
    assert reason([rec(1, 0.4), rec(2, 1.0, solved=True, tampered=True)]) == "continue"


def test_repeated_tampering_stops():
    h = [rec(1, 0.4, tampered=True), rec(2, 0.5), rec(3, 0.6, tampered=True)]
    assert reason(h, max_tamper=2) == "tampering"


def test_iteration_budget():
    assert reason([rec(1, 0.1), rec(2, 0.2), rec(3, 0.3)], max_iterations=3) == "budget_iterations"


def test_token_budget_uses_the_total():
    assert reason([rec(1, 0.1, tokens=600), rec(2, 0.2, tokens=500)], max_tokens=1000) == "budget_tokens"
    assert reason([rec(1, 0.1, tokens=400), rec(2, 0.2, tokens=500)], max_tokens=1000) == "continue"


def test_cost_budget_spent():
    assert reason([rec(1, 0.1, cost=0.03), rec(2, 0.2, cost=0.03)], max_cost_usd=0.05) == "budget_cost"


def test_cost_budget_cannot_afford_another_iteration():
    # spent 0.04 of 0.05, and the last iteration cost 0.02: the next one would overspend
    assert reason([rec(1, 0.1, cost=0.02), rec(2, 0.2, cost=0.02)], max_cost_usd=0.05) == "budget_cost"
    assert reason([rec(1, 0.1, cost=0.01), rec(2, 0.2, cost=0.01)], max_cost_usd=0.05) == "continue"


def test_time_budget():
    assert reason([rec(1, 0.1, elapsed=40), rec(2, 0.2, elapsed=25)], max_seconds=60) == "budget_time"


def test_none_limits_are_not_checked():
    h = [rec(1, 0.1, tokens=10**9, cost=99.0, elapsed=10**6), rec(2, 0.2, tokens=10**9, cost=99.0, elapsed=10**6)]
    assert reason(h, max_tokens=None, max_cost_usd=None, max_seconds=None) == "continue"


def test_no_change():
    assert reason([rec(1, 0.3, h="a"), rec(2, 0.3, h="a")]) == "no_change"


def test_oscillation():
    assert reason([rec(1, 0.5, h="a"), rec(2, 0.5, h="b"), rec(3, 0.5, h="a")], patience=5) == "oscillation"


def test_oscillation_wins_over_no_progress():
    assert reason([rec(1, 0.5, h="a"), rec(2, 0.5, h="b"), rec(3, 0.5, h="a")], patience=2) == "oscillation"


def test_no_progress_after_patience():
    h = [rec(1, 0.6), rec(2, 0.5), rec(3, 0.6)]
    assert reason(h, patience=2) == "no_progress"


def test_progress_resets_patience():
    h = [rec(1, 0.6), rec(2, 0.5), rec(3, 0.7)]
    assert reason(h, patience=2) == "continue"


def test_patience_needs_enough_history():
    assert reason([rec(1, 0.6), rec(2, 0.5)], patience=2) == "continue"


def test_budget_checked_before_no_change():
    assert reason([rec(1, 0.3, h="a"), rec(2, 0.3, h="a")], max_iterations=2) == "budget_iterations"


def test_tampering_checked_before_budget():
    h = [rec(1, 0.4, tampered=True), rec(2, 0.5, tampered=True)]
    assert reason(h, max_iterations=2, max_tamper=2) == "tampering"
