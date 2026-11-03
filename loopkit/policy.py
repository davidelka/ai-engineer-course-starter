"""Reference stop policy. Exercise 3 in lesson 7 asks you to write your own in mine.py.

The policy reads the whole history after every iteration and answers one question:
spend another iteration, or stop, and why. Rules are checked in a fixed order, so
the reason is deterministic when several apply.
"""

from __future__ import annotations

from .types import Budget, IterationRecord, StopDecision

STOP_REASONS = ("solved", "tampering", "budget_iterations", "budget_tokens", "budget_cost", "budget_time",
                "no_change", "oscillation", "no_progress")


def should_stop(history: list[IterationRecord], budget: Budget) -> StopDecision:
    """Order of the rules (the first that applies wins):

    1. empty history                                   -> continue
    2. last iteration solved and not tampered          -> "solved"
    3. tampered iterations >= budget.max_tamper        -> "tampering"
    4. iterations >= budget.max_iterations             -> "budget_iterations"
    5. total tokens >= budget.max_tokens               -> "budget_tokens"
    6. total cost >= budget.max_cost_usd, OR total cost + last iteration's cost
       > budget.max_cost_usd (another iteration like the last one would overspend)
                                                       -> "budget_cost"
    7. total elapsed >= budget.max_seconds             -> "budget_time"
    8. last candidate_hash == the one before it        -> "no_change"
    9. last candidate_hash equals any earlier one      -> "oscillation"
    10. more than `patience` iterations, and the best score of the last `patience`
        iterations is not higher than the best score before them -> "no_progress"
    11. otherwise                                      -> continue
    Limits that are None are not checked.
    """
    if not history:
        return StopDecision(False, "continue")
    last = history[-1]
    if last.solved and not last.tampered:
        return StopDecision(True, "solved")
    if sum(1 for r in history if r.tampered) >= budget.max_tamper:
        return StopDecision(True, "tampering")
    if len(history) >= budget.max_iterations:
        return StopDecision(True, "budget_iterations")
    tokens = sum(r.tokens for r in history)
    if budget.max_tokens is not None and tokens >= budget.max_tokens:
        return StopDecision(True, "budget_tokens")
    cost = sum(r.cost_usd for r in history)
    if budget.max_cost_usd is not None and (cost >= budget.max_cost_usd or cost + last.cost_usd > budget.max_cost_usd):
        return StopDecision(True, "budget_cost")
    elapsed = sum(r.elapsed_s for r in history)
    if budget.max_seconds is not None and elapsed >= budget.max_seconds:
        return StopDecision(True, "budget_time")
    if len(history) >= 2 and last.candidate_hash == history[-2].candidate_hash:
        return StopDecision(True, "no_change")
    if any(r.candidate_hash == last.candidate_hash for r in history[:-2]):
        return StopDecision(True, "oscillation")
    p = budget.patience
    if p > 0 and len(history) > p:
        recent = max(r.score for r in history[-p:])
        before = max(r.score for r in history[:-p])
        if recent <= before:
            return StopDecision(True, "no_progress")
    return StopDecision(False, "continue")
