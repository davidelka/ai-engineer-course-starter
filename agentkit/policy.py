"""The reference stop policy (lesson 15, exercise 3 asks you to write it in mine.py).

The agent calls should_stop(history, budget) after EVERY step, including the step in
which the model answered. The policy is a pure function of the history, so it is easy
to test and to swap: Agent(policy=mine.should_stop).

Why each rule exists:
  final_answer / gave_up   the normal ends. An explicit give-up is a SUCCESSFUL stop:
                           the agent knew it could not finish and said why.
  max_steps                the hard ceiling. Every loop needs one, even with the others.
  budget_tokens / _cost    money. The cost rule also looks one step ahead: if the next
                           step costs what the last one did, would it overspend?
  budget_time              latency promises to a user (and stuck tools).
  repetition               the same call with the same arguments, again and again: the
                           model is stuck, and nothing new can come back.
  tool_errors              every call failing, step after step: the tools are down or the
                           model cannot form valid calls. Stop before burning the budget.
  no_progress              the subtle loop: calls DIFFER (so repetition misses it), but no
                           step learns anything new (same results, or only errors).
"""

from __future__ import annotations

import hashlib
from collections import Counter

from llmkit.types import ToolCall, ToolResult
from toolkit.confirm import call_fingerprint

from .types import Budget, StepRecord, StopDecision

STOP_REASONS = ("final_answer", "gave_up", "max_steps", "budget_tokens", "budget_cost", "budget_time",
                "repetition", "tool_errors", "no_progress",
                # set by the agent itself, not by the policy:
                "refusal", "max_tokens", "model_error")
SUCCESS_STOPS = ("final_answer", "gave_up")


def fingerprint(call: ToolCall) -> str:
    """Short, stable id of a call: same tool + same arguments (canonical JSON) = same id."""
    return call_fingerprint(call)[:12]


def result_hash(result: ToolResult) -> str | None:
    """None for a failed call; otherwise a short hash of the result text."""
    if result.is_error:
        return None
    return hashlib.sha256(result.text.encode()).hexdigest()[:12]


def should_stop(history: list[StepRecord], budget: Budget) -> StopDecision:
    """Rules in a fixed order; the first that applies wins:

    1. empty history                                     -> continue
    2. last step final                                   -> "final_answer"
    3. last step gave_up                                 -> "gave_up"
    4. len(history) >= budget.max_steps                  -> "max_steps"
    5. sum(tokens) >= budget.max_tokens                  -> "budget_tokens"
    6. cost >= max_cost_usd, or cost + last step's cost > max_cost_usd
                                                         -> "budget_cost"
    7. sum(elapsed_s) >= budget.max_seconds              -> "budget_time"
    8. a fingerprint of the LAST step occurs >= repeat_limit times in the whole history
                                                         -> "repetition"
    9. the last max_consecutive_errors steps each had calls and ALL of them failed
                                                         -> "tool_errors"
    10. the last no_progress_steps steps each produced no new successful result hash
        (a hash is new if no earlier step, in the whole history, produced it)
                                                         -> "no_progress"
    11. otherwise                                        -> continue
    """
    if not history:
        return StopDecision(False, "continue")
    last = history[-1]
    if last.final:
        return StopDecision(True, "final_answer", "the model answered without asking for tools")
    if last.gave_up:
        return StopDecision(True, "gave_up", "the model called give_up")
    if len(history) >= budget.max_steps:
        return StopDecision(True, "max_steps", f"{len(history)} steps (limit {budget.max_steps})")
    tokens = sum(s.tokens for s in history)
    if budget.max_tokens is not None and tokens >= budget.max_tokens:
        return StopDecision(True, "budget_tokens", f"{tokens:,} tokens (limit {budget.max_tokens:,})")
    cost = sum(s.cost_usd for s in history)
    if budget.max_cost_usd is not None:
        if cost >= budget.max_cost_usd:
            return StopDecision(True, "budget_cost", f"${cost:.5f} spent (limit ${budget.max_cost_usd:.5f})")
        if cost + last.cost_usd > budget.max_cost_usd:
            return StopDecision(True, "budget_cost", f"${cost:.5f} spent; another step like the last "
                                                     f"(${last.cost_usd:.5f}) would pass ${budget.max_cost_usd:.5f}")
    elapsed = sum(s.elapsed_s for s in history)
    if budget.max_seconds is not None and elapsed >= budget.max_seconds:
        return StopDecision(True, "budget_time", f"{elapsed:.1f}s (limit {budget.max_seconds:g}s)")
    counts = Counter(fp for s in history for fp in s.fingerprints)
    for name, fp in zip(last.calls, last.fingerprints):
        if counts[fp] >= budget.repeat_limit:
            return StopDecision(True, "repetition", f"{name} called {counts[fp]} times with identical arguments "
                                                    f"(limit {budget.repeat_limit})")
    k = budget.max_consecutive_errors
    if k > 0 and len(history) >= k and all(s.calls and s.errors == len(s.calls) for s in history[-k:]):
        return StopDecision(True, "tool_errors", f"every tool call failed in the last {k} steps")
    w = budget.no_progress_steps
    if w > 0 and len(history) >= w:
        seen: set[str] = set()
        progress: list[bool] = []
        for s in history:
            new = {h for h in s.result_hashes if h is not None and h not in seen}
            progress.append(bool(new))
            seen |= new
        if not any(progress[-w:]):
            return StopDecision(True, "no_progress", f"no new information in the last {w} steps")
    return StopDecision(False, "continue")
