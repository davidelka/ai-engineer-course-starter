"""Your code for lesson 15. Each part is checked by tests in ./tests.

Reference versions live in agentkit/ (policy.py, evaluate.py, memory.py).
Try not to peek before your tests pass.

    python -m pytest -q labs/15-agent-loops/tests

Each docstring is a contract: what goes in, what comes out, and the rules the result must follow.
When you are stuck, HINTS.md has graded hints for every function (direction, structure, full algorithm).
"""

from __future__ import annotations

import json  # noqa: F401
from collections import Counter  # noqa: F401
from typing import Optional

from agentkit.memory import is_cleared, placeholder  # noqa: F401  (exercise 7)
from agentkit.types import Budget, StepRecord, StopDecision  # noqa: F401
from llmkit.types import Message, ToolResult  # noqa: F401

ROUTES = ("auto_approve", "needs_manager", "needs_security")
SUCCESS_STOPS = ("final_answer", "gave_up")
LOCAL_TOOLS = ("note",)  # the scratchpad tool is not a "tool call" for the metrics
REQUEST_FIELDS = {"employee": "employee_id", "system": "system", "access_level": "access_level",
                  "duration_days": "duration_days", "route": "route"}  # gold key -> key in the create result


# ------------------------------------------------------------------ exercise 3: the stop policy
def should_stop(history: list[StepRecord], budget: Budget) -> StopDecision:
    """Decide after every step: continue, or stop and why. Pure function of the history.

    Each StepRecord holds PER-STEP values (read its docstring, and Budget's for every limit).
    result_hashes is None for a failed call and for the local `note` tool (bookkeeping, not
    new information).

    Returns StopDecision(False, "continue") for an empty history or when no rule applies.
    Otherwise stop=True with one of these reasons; when several apply, the FIRST in this list wins:
        final_answer, gave_up, max_steps, budget_tokens, budget_cost, budget_time,
        repetition, tool_errors, no_progress
    Rules the tests depend on: a limit set to None (or 0 for the last two) is off; reaching a
    limit stops (>=); budget_cost also stops when one more step as expensive as the last would go
    over the limit; repetition counts every occurrence of a fingerprint of the LAST step across
    the whole history; a step "fails" only if it had calls and all of them failed; a step "makes
    progress" only if it produced a successful result hash never seen earlier in the run.
    detail: one non-empty human-readable line when stop is True (which limit, the numbers).

    Stuck? HINTS.md -> should_stop
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement should_stop")


# ------------------------------------------------------------------ exercise 4: trajectory metrics
def score_trajectory(records: list[dict], gold: dict, task_id: str = "") -> dict:
    """Score ONE run against its gold outcome. `records` are the trajectory dicts of one run:
    {"type": "run"}, {"type": "step", "calls": [...], "results": [...]}, ..., {"type": "stop"}.

    A step record has calls = [{"id", "name", "arguments", "fp"}] and results = [{"id", "name",
    "is_error", "hash", "text", ...}], aligned by position. The stop record has "reason",
    "text" (the final answer), "cost_usd", "input_tokens", "output_tokens". Tool results are
    JSON text. Calls to LOCAL_TOOLS do not count anywhere.

    Returns a dict with: task_id, stop_reason ("missing_stop" if there is no stop record), steps,
    tool_calls, errors, redundant_calls (a call repeating one that already SUCCEEDED earlier; a
    retry after a failure is not redundant), efficiency (gold["optimal_calls"] / tool_calls,
    capped at 1.0; with no tool calls 1.0 if optimal is 0, else 0.0; None without optimal_calls), evidence_conflict (the answer
    names a route from ROUTES, check_policy succeeded, and none of the named routes is one that
    check_policy returned), requests_created (successful create_access_request calls), cost_usd,
    tokens (input + output), reasons, success (True when reasons is empty).

    reasons: one free-wording string per problem: a non-success stop (SUCCESS_STOPS); a
    gold["required_tools"] tool never succeeded; a gold["forbidden_tools"] tool succeeded; the
    request outcome is wrong (outcome "request_created" needs exactly one request whose fields
    match gold["request"] via REQUEST_FIELDS; any other outcome needs none); a gold["answer_contains"]
    string is missing; none of gold["answer_contains_any"] appears (both case-insensitive);
    evidence_conflict. A wrong request counts once per bad field.

    Stuck? HINTS.md -> score_trajectory
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement score_trajectory")


def summarize_scores(scores: list[dict]) -> dict:
    """Aggregate score_trajectory results. Return a dict with:
      tasks, successes, success_rate (0.0 when there are no tasks),
      mean_steps, mean_tool_calls (per task),
      redundant_calls (total), redundancy_rate (redundant / total tool calls; 0.0 if no calls),
      errors (total), mean_efficiency (mean over scores whose efficiency is not None, else None),
      evidence_conflicts (count of scores with evidence_conflict),
      cost_usd (total), cost_per_success (total cost / successes, None if no successes),
      stop_reasons (dict reason -> count), failed (task_ids that did not succeed, in order).

    Stuck? HINTS.md -> summarize_scores
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement summarize_scores")


# ------------------------------------------------------------------ exercise 7: memory trimming
def clear_old_tool_results(messages: list[Message], keep: int) -> tuple[list[Message], int]:
    """Return (new_messages, number_of_results_cleared_by_this_call).

    A tool-result turn is a user Message with at least one ToolResult (m.tool_results).
      - The last `keep` tool-result turns stay exactly as they are; keep <= 0 clears them all.
      - In older ones, every result not already cleared (is_cleared) becomes a cleared result
        whose content is placeholder(result), with the SAME call_id, name and is_error.
        Count each one; already-cleared results are not counted again.
      - Other parts of those messages (text Blocks) stay in place, and raw/raw_provider are kept.
      - The input list and its Message objects are never modified; unchanged messages may be the
        same objects in the output.

    Stuck? HINTS.md -> clear_old_tool_results
    """
    # TODO(ex7)
    raise NotImplementedError("exercise 7: implement clear_old_tool_results")
