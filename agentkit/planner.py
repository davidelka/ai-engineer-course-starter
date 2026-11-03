"""Plan-then-act: a structured plan first (llmkit.structured, lesson 3), then the act loop.

    plan = make_plan(llm, task, tools)              -> PlanOutcome(plan, tokens, cost)
    new  = replan(llm, task, tools, plan, observations, reason)

The planner sees the tool NAMES and DESCRIPTIONS, never runs anything, and returns a
Plan object (goal, steps with tool and dependencies, done_when). The agent puts the
plan in the system prompt of the act loop. When the act loop hits failures that the
plan did not expect, the agent asks for a revised plan with the observations so far.

Why plan at all? A plan exposes the whole intended path BEFORE any side effect (you can
log it, show it, or have a human approve it), lets independent reads run in parallel,
and keeps a long task on track. The price: one more model call, and a plan made before
seeing any data can be wrong; that is what replanning is for.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from llmkit.structured import StructuredError, complete_structured
from llmkit.types import ChatRequest, Message, Tool

from .types import Plan

PLANNER_SYSTEM = (
    "You are the PLANNER of an agent that serves Acme employees. You do not run tools; you write a plan that "
    "another step will execute with the tools listed below. Rules: use the fewest steps that reach the goal; "
    "every fact about employees, systems, grants and policy must come from a tool, never from memory; steps "
    "with no dependencies between them can run in parallel, so give them depends_on []; include a side-effect "
    "tool (one that files or changes something) ONLY if the user explicitly asked for that action, and only "
    "after the steps that check it is appropriate; end with a step (tool null) that answers the user.")


@dataclass
class PlanOutcome:
    plan: Optional[Plan]
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: str = ""

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def tools_text(tools: list[Tool]) -> str:
    out = []
    for t in tools:
        first = t.description.split(". ")[0].rstrip(".")
        args = ", ".join((t.input_schema.get("properties") or {}).keys())
        out.append(f"- {t.name}({args}): {first}.")
    return "\n".join(out)


def _run(llm, prompt: str, tools: list[Tool], max_tokens: int) -> PlanOutcome:
    req = ChatRequest(messages=[Message("user", prompt)], system=PLANNER_SYSTEM + "\n\nTools:\n" + tools_text(tools),
                      max_tokens=max_tokens)
    try:
        r = complete_structured(llm, req, Plan, max_repairs=1)
    except StructuredError as exc:
        res = exc.result
        return PlanOutcome(None, getattr(res, "input_tokens", 0), getattr(res, "output_tokens", 0),
                           getattr(res, "cost_usd", 0.0), error=f"{exc.stage}: {exc}")
    return PlanOutcome(r.value, r.input_tokens, r.output_tokens, r.cost_usd)  # type: ignore[arg-type]


def make_plan(llm, task: str, tools: list[Tool], max_tokens: int = 1024) -> PlanOutcome:
    return _run(llm, f"<task>\n{task}\n</task>\nWrite the plan.", tools, max_tokens)


def replan(llm, task: str, tools: list[Tool], plan: Optional[Plan], observations: list[dict], reason: str,
           max_tokens: int = 1024) -> PlanOutcome:
    obs = "\n".join(f"- {o['name']}({json.dumps(o.get('arguments', {}), ensure_ascii=False)}) -> "
                    f"{'ERROR: ' if o.get('is_error') else ''}{o.get('text', '')[:300]}" for o in observations[-8:])
    prompt = (f"<task>\n{task}\n</task>\n<previous_plan>\n{plan.render() if plan else '(none)'}\n</previous_plan>\n"
              f"<observations>\n{obs}\n</observations>\n"
              f"The previous plan ran into a problem: {reason}. Write a REVISED plan for the remaining work. "
              "Do not repeat steps that already succeeded. If the task cannot be completed (for example the "
              "person is ambiguous or does not exist), plan a single final step that explains why and asks the "
              "user for what is missing.")
    return _run(llm, prompt, tools, max_tokens)
