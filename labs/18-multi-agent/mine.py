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

    decision.routes       domains the model chose, most important first (may repeat, may be empty,
                          may contain a domain that is not in `allowed`)
    decision.confidence   0.0 - 1.0
    decision.clarifying_question   a question the model proposed, or None

    Rules, in this order:
      1. targets = decision.routes with duplicates removed (keep the FIRST occurrence and the order),
         keeping only domains in `allowed`, then cut to the first `max_targets`.
      2. question = decision.clarifying_question if it is a non-empty string, else DEFAULT_QUESTION.
      3. no targets left                      -> RouteChoice("clarify", [], question, why)
      4. decision.confidence < threshold      -> RouteChoice("clarify", [], question, why)
         (exactly equal to the threshold routes)
      5. otherwise                            -> RouteChoice("route", targets, None, why)

    why: a short human-readable reason (tests only check it is a non-empty string).
    Note the order: an empty route list asks even when confidence is high, and a low confidence
    asks even when the routes look fine.
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement decide_route")


# ------------------------------------------------------------------ exercise 4: the handoff contract
def make_handoff_brief(summary: dict, original_task: str, side_effects: list[dict], *,
                       from_agent: str = "agent", to_agent: str = "agent") -> str:
    """Check a handoff summary and render the brief the next agent will see, or refuse it.

    summary (the transfer tool's arguments, HandoffSummary.model_dump()):
        original_request: str, goal: str, facts: [{"claim": str, "source": str}],
        actions_taken: [str], constraints: [str], open_questions: [str]
    original_task: the user's real message.  side_effects: dicts returned by side-effect tools
    in this chain so far, e.g. {"id": "AR-00001", "system": "figma", ...}.

    Collect EVERY problem (do not stop at the first), in this order:
      1. normalize = collapse all whitespace runs to one space, strip, lowercase.
         normalize(summary["original_request"]) != normalize(original_task)
             -> "original_request must be the user's message verbatim"
      2. summary["goal"] empty or only whitespace          -> "goal is empty"
      3. for each fact i (1-based): empty claim            -> f"fact {i} has no claim"
                                    empty source           -> f"fact {i} has no source"
      4. for each clause in constraint_clauses(original_task) (already imported: for every sentence
         with a trigger such as "do not", "only if", "not yet", the text from the trigger to the end
         of the sentence), it must appear, normalized, as a substring of at least one normalized
         item of summary["constraints"]    -> f"constraint missing: {clause!r}"
      5. for each side effect with an "id": that id must appear (exact, case-sensitive) somewhere in
         the actions_taken items           -> f"actions_taken does not mention {id}"
    If there is any problem: raise HandoffError(problems) (a list of the strings above).
    Otherwise return render_brief(summary, from_agent, to_agent) (already imported; it writes the
    <handoff> block with <original_request>, <your_part>, <facts>, <actions_taken>, <constraints>
    and <open_questions>).
    Missing keys count as empty (use .get with defaults).
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement make_handoff_brief")


# ------------------------------------------------------------------ exercise 6: who spent what
def aggregate_runs(records: list[dict]) -> dict:
    """Add up a multi-agent run (or many) from trajectory records of several agents.

    records: agentkit trajectory dicts from several runs, mixed together. Group them by "run_id".
    In each run: the "run" record has "agent" (name) and "role" ("coordinator" or "worker";
    missing -> "worker"); the "stop" record has input_tokens, output_tokens, cost_usd, elapsed_s
    (missing -> 0); "step" records have "calls" (a list of {"name": ...}). Every record may have
    "ts" (milliseconds since the epoch).

    Return:
    {
      "agents": {name: {"role": role of the first run seen for that name,
                        "runs": number of runs, "steps": number of step records,
                        "tool_calls": calls whose name is not in LOCAL_TOOLS,
                        "input_tokens", "output_tokens", "tokens" (= in + out),
                        "cost_usd", "elapsed_s" (sums over that agent's runs),
                        "cost_share": cost_usd / total cost (0.0 if the total is 0)}},
      "runs": number of distinct run_ids,
      "total_tokens": sum over agents, "total_cost_usd": sum over agents,
      "coordination_cost_usd": cost of runs whose role is in COORDINATION_ROLES,
      "coordination_share": coordination_cost_usd / total_cost_usd (0.0 if total is 0),
      "wall_s": (max ts - min ts) / 1000 over ALL records that have "ts" (0.0 if none),
      "agent_s": sum of elapsed_s over all agents,
      "parallelism": agent_s / wall_s if wall_s > 0 else 1.0,
    }
    parallelism > 1 means agents ran at the same time (fan-out); about 1 means one after another.
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement aggregate_runs")
