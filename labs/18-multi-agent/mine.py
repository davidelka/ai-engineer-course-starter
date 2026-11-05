"""Your code for lesson 18. Each part is checked by tests in ./tests.

Reference versions live in multikit/ (router.py, handoff.py, attribution.py).
Try not to peek before your tests pass.

    python -m pytest -q labs/18-multi-agent/tests
"""

from __future__ import annotations

import re  # noqa: F401
from collections import defaultdict  # noqa: F401
from typing import Optional  # noqa: F401

from multikit.handoff import HandoffError, constraint_clauses, render_brief  # noqa: F401  (exercise 4)
from multikit.router import DEFAULT_QUESTION, RouteChoice, RouteDecision  # noqa: F401  (exercise 2)

DOMAINS = ("hr", "it_access", "oncall")
COORDINATION_ROLES = ("coordinator",)
LOCAL_TOOLS = ("note",)


# ------------------------------------------------------------------ exercise 2: the router's decision
def decide_route(decision: RouteDecision, *, threshold: float = 0.6, allowed: tuple[str, ...] = DOMAINS,
                 max_targets: int = 1) -> RouteChoice:
    """Turn the router model's RouteDecision into an action. CODE makes the final call, not the model.

    Receives a RouteDecision (routes: list[str], most important first, may repeat, may be empty or
    hold unknown domains; confidence: 0.0-1.0; clarifying_question: str | None).
    Returns RouteChoice(action, targets, question, why):
      - "route": targets = the model's domains that are in `allowed`, no duplicates, model order kept,
        at most `max_targets`; question is None.
      - "clarify": targets == []; question = the model's question, or DEFAULT_QUESTION when it is
        None, empty or only whitespace.
    Clarify when no valid target is left OR confidence < threshold (equal to the threshold routes).
    why: a non-empty human-readable reason.

    Stuck? HINTS.md -> decide_route
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement decide_route")


# ------------------------------------------------------------------ exercise 4: the handoff contract
def make_handoff_brief(summary: dict, original_task: str, side_effects: list[dict], *,
                       from_agent: str = "agent", to_agent: str = "agent") -> str:
    """Check a handoff summary and render the brief the next agent will see, or refuse it.

    summary (HandoffSummary.model_dump()): original_request, goal, facts [{"claim", "source"}],
    actions_taken [str], constraints [str], open_questions [str]. Missing keys count as empty.
    original_task: the user's real message. side_effects: dicts from side-effect tools so far,
    e.g. {"id": "AR-00001", "system": "figma", ...}.

    Returns render_brief(summary, from_agent, to_agent) when the summary is valid.
    Otherwise raises HandoffError(problems): a list with EVERY problem, in this order and wording:
      "original_request must be the user's message verbatim"   (ignoring case and whitespace)
      "goal is empty"
      f"fact {i} has no claim" / f"fact {i} has no source"      (i is 1-based)
      f"constraint missing: {clause!r}"   (each clause of constraint_clauses(original_task))
      f"actions_taken does not mention {id}"   (each side effect id, exact match)

    Stuck? HINTS.md -> make_handoff_brief
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement make_handoff_brief")


# ------------------------------------------------------------------ exercise 6: who spent what
def aggregate_runs(records: list[dict]) -> dict:
    """Add up a multi-agent run (or many) from trajectory records of several agents.

    records: agentkit trajectory dicts from several runs mixed together, each with "run_id".
    Per run: a "run" record ("agent", "role" default "worker"), a "stop" record (input_tokens,
    output_tokens, cost_usd, elapsed_s, default 0), "step" records ("calls": [{"name": ...}]).
    Any record may have "ts" (ms since the epoch).

    Returns a dict with:
      "agents": {name: {"role", "runs", "steps", "tool_calls", "input_tokens", "output_tokens",
                        "tokens", "cost_usd", "elapsed_s", "cost_share"}},
      "runs", "total_tokens", "total_cost_usd", "coordination_cost_usd", "coordination_share",
      "wall_s", "agent_s", "parallelism".
    tool_calls excludes LOCAL_TOOLS; coordination = runs whose role is in COORDINATION_ROLES.
    Shares are 0.0 when the total cost is 0; wall_s is 0.0 with no ts; parallelism is 1.0 when
    wall_s is 0. Empty input must work.

    Stuck? HINTS.md -> aggregate_runs
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement aggregate_runs")
