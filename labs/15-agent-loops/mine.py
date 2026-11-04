"""Your code for lesson 15. Each part is checked by tests in ./tests.

Reference versions live in agentkit/ (policy.py, evaluate.py, memory.py).
Try not to peek before your tests pass.

    python -m pytest -q labs/15-agent-loops/tests
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

    Each StepRecord holds PER-STEP values: calls (tool names), fingerprints (one per call,
    same tool + same arguments = same string), result_hashes (one per call; None when that
    call failed, and also None for the local `note` tool, whose result is bookkeeping and
    not new information), errors, final, gave_up, tokens, cost_usd, elapsed_s.

    Check the rules IN THIS ORDER and return the first that applies:
      1. history is empty                                  -> StopDecision(False, "continue")
      2. last step .final                                  -> stop, "final_answer"
      3. last step .gave_up                                -> stop, "gave_up"
      4. len(history) >= budget.max_steps                  -> stop, "max_steps"
      5. budget.max_tokens is not None and the sum of tokens >= it      -> stop, "budget_tokens"
      6. budget.max_cost_usd is not None and EITHER total cost >= it, OR total cost + the
         last step's cost > it (another step like the last would overspend) -> stop, "budget_cost"
      7. budget.max_seconds is not None and the sum of elapsed_s >= it  -> stop, "budget_time"
      8. some fingerprint of the LAST step occurs >= budget.repeat_limit times across the
         whole history (count every occurrence, the last step included) -> stop, "repetition"
      9. k = budget.max_consecutive_errors > 0, len(history) >= k, and each of the last k
         steps had at least one call and ALL its calls failed (errors == len(calls))
                                                           -> stop, "tool_errors"
     10. w = budget.no_progress_steps > 0, len(history) >= w, and none of the last w steps
         produced a NEW successful result hash. Walk the history from the start with a set
         of seen hashes: a step "made progress" if it has a hash that is not None and not
         seen before (then add its hashes). A final step has no calls and makes no progress,
         but rule 2 already returned for it.               -> stop, "no_progress"
     11. otherwise                                         -> StopDecision(False, "continue")

    detail: one human-readable line (which limit and the numbers); tests only check that
    it is a non-empty string when stop is True.
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement should_stop")


# ------------------------------------------------------------------ exercise 4: trajectory metrics
def score_trajectory(records: list[dict], gold: dict, task_id: str = "") -> dict:
    """Score ONE run against its gold outcome. `records` are the trajectory dicts of one run:
    {"type": "run"}, {"type": "step", "calls": [...], "results": [...]}, ..., {"type": "stop"}.

    A step record has calls = [{"id", "name", "arguments", "fp"}] and results = [{"id", "name",
    "is_error", "hash", "text", ...}], aligned by position. The stop record has "reason",
    "text" (the final answer), "cost_usd", "input_tokens", "output_tokens".

    Ignore calls whose name is in LOCAL_TOOLS everywhere below. Then return a dict with:
      task_id            the argument
      stop_reason        stop["reason"] ("missing_stop" if there is no stop record)
      steps              number of step records
      tool_calls         number of (non-local) calls
      errors             number of results with is_error
      redundant_calls    calls whose fp already appeared EARLIER in the run with a successful
                         (not is_error) result. A repeat after a failure is a retry, not redundant.
      efficiency         gold["optimal_calls"] / tool_calls, capped at 1.0; 1.0 if both are 0;
                         0.0 if tool_calls is 0 but optimal is not; None if gold has no optimal_calls
      evidence_conflict  True if the answer (case-insensitive) names at least one route from ROUTES,
                         check_policy succeeded at least once, and NONE of the named routes is a
                         route that check_policy returned (parse the result text as JSON, key "route")
      requests_created   number of successful create_access_request calls
      cost_usd, tokens   from the stop record (tokens = input + output)
      reasons            list of strings, one per problem found (wording is free), for:
                         - stop_reason not in SUCCESS_STOPS
                         - a tool in gold["required_tools"] with no successful call
                         - a tool in gold["forbidden_tools"] with a successful call
                         - gold["outcome"] == "request_created": not exactly one created request,
                           or a field of gold["request"] that differs from the created request
                           (parse the create result text as JSON; map keys with REQUEST_FIELDS)
                         - any other outcome: one or more requests created
                         - a string of gold["answer_contains"] missing from the answer (case-insensitive)
                         - gold["answer_contains_any"] given and none of its strings in the answer
                         - evidence_conflict
      success            True when reasons is empty
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
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement summarize_scores")


# ------------------------------------------------------------------ exercise 7: memory trimming
def clear_old_tool_results(messages: list[Message], keep: int) -> tuple[list[Message], int]:
    """Return (new_messages, number_of_results_cleared_by_this_call).

    A tool-result turn is a user Message with at least one ToolResult (m.tool_results).
      - The last `keep` tool-result turns stay exactly as they are.
      - In every older one, replace each ToolResult that is not already cleared
        (is_cleared(result) is False) by ToolResult(call_id, placeholder(result),
        is_error=..., name=...): SAME call_id, name and is_error. Count each one.
      - Keep other parts of those messages (text Blocks) in place, and keep raw/raw_provider.
      - keep <= 0 means clear every tool-result turn.
      - Do NOT modify the input list or its Message objects; unchanged messages may be the
        same objects in the output.
    """
    # TODO(ex7)
    raise NotImplementedError("exercise 7: implement clear_old_tool_results")
