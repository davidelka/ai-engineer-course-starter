"""Pattern 3: handoffs. Control moves from agent to agent; nobody sits above them.

A triage agent reads the request and calls transfer_to_<specialist>. That specialist does its
part and, if another domain is left, calls transfer_to_<next>. The LAST agent answers the user.
This is the shape of OpenAI's Agents SDK handoffs and LangGraph's swarm: a handoff is a tool
call whose arguments say where to go and what to carry.

What to carry is the whole design problem. Passing the full transcript makes every agent pay
for everything before it (and drags the previous agent's tools and mistakes along). Passing
nothing loses the request. multikit passes a STRUCTURED SUMMARY (the transfer tool's input
schema, HandoffSummary), and make_handoff_brief() checks it before the transfer is allowed:

    original_request   the user's message, VERBATIM (paraphrases lose constraints)
    goal               what the next agent must do
    facts              what is already known, each with its source
    actions_taken      every side effect so far (a filed request, with its id), so nobody redoes it
    constraints        every "do not / only if / not yet ..." clause of the request, word for word
    open_questions     what nobody has answered yet

A rejected summary comes back to the transferring agent as a tool ERROR listing the problems,
so it can fix it, exactly like a validation error in lesson 3. make_handoff_brief() is the
reference for lesson 18, exercise 4 (mine.py).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from pydantic import BaseModel, Field

from agentkit import Agent, Budget, should_stop
from agentkit.types import StepRecord, StopDecision
from toolkit import Registry, ToolError, ToolSpec

from .attribution import MultiResult, agent_run
from .domains import DOMAIN_INFO, DOMAINS
from .specialists import SPECIALISTS, specialist_registry

TRIGGERS = ("do not", "don't", "only if", "only after", "without", "not yet", "never")
_TRIGGER_RX = re.compile(r"\b(" + "|".join(re.escape(t) for t in TRIGGERS) + r")\b", re.I)


class Fact(BaseModel):
    claim: str = Field(description="One fact that is already known, as a short sentence")
    source: str = Field(description="Where it came from: a tool name, a document id, or the agent that found it")


class HandoffSummary(BaseModel):
    original_request: str = Field(description="The user's original message, copied VERBATIM (not paraphrased)")
    goal: str = Field(description="What the next agent must do: the part of the request it owns")
    facts: list[Fact] = Field(description="Facts already established, each with its source; [] if none")
    actions_taken: list[str] = Field(description="Every action with a side effect done so far (e.g. 'Filed AR-00003 "
                                                 "for figma editor, route needs_manager'); [] if none")
    constraints: list[str] = Field(description="Every constraint in the request ('do not file anything', 'only if it "
                                               "is auto-approved'), copied word for word; [] if none")
    open_questions: list[str] = Field(description="Questions still unanswered; [] if none")


class HandoffError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def _norm(s: str) -> str:
    return " ".join(str(s).split()).lower()


def constraint_clauses(text: str) -> list[str]:
    """Each sentence's text from its first trigger phrase to the end, without final punctuation."""
    out = []
    for sent in re.split(r"(?<=[.?!])\s+", text.strip()):
        m = _TRIGGER_RX.search(sent)
        if m:
            out.append(sent[m.start():].strip().rstrip(".?!").strip())
    return out


def render_brief(summary: dict, from_agent: str, to_agent: str) -> str:
    def block(tag: str, items: list[str]) -> str:
        body = "\n".join(f"- {x}" for x in items) if items else "- (none)"
        return f"<{tag}>\n{body}\n</{tag}>"
    facts = [f"{f['claim']} (source: {f['source']})" for f in summary.get("facts") or []]
    return "\n".join([
        f'<handoff from="{from_agent}" to="{to_agent}">',
        "<original_request>", str(summary.get("original_request", "")).strip(), "</original_request>",
        "<your_part>", str(summary.get("goal", "")).strip(), "</your_part>",
        block("facts", facts),
        block("actions_taken", list(summary.get("actions_taken") or [])),
        block("constraints", list(summary.get("constraints") or [])),
        block("open_questions", list(summary.get("open_questions") or [])),
        "</handoff>",
    ])


def make_handoff_brief(summary: dict, original_task: str, side_effects: list[dict], *,
                       from_agent: str = "agent", to_agent: str = "agent") -> str:
    """See labs/18-multi-agent/mine.py for the exact contract (this is the reference)."""
    problems: list[str] = []
    if _norm(summary.get("original_request", "")) != _norm(original_task):
        problems.append("original_request must be the user's message verbatim")
    if not str(summary.get("goal", "")).strip():
        problems.append("goal is empty")
    for i, f in enumerate(summary.get("facts") or [], 1):
        if not str(f.get("claim", "")).strip():
            problems.append(f"fact {i} has no claim")
        if not str(f.get("source", "")).strip():
            problems.append(f"fact {i} has no source")
    cons = [_norm(c) for c in summary.get("constraints") or []]
    for clause in constraint_clauses(original_task):
        if not any(_norm(clause) in c for c in cons):
            problems.append(f"constraint missing: {clause!r}")
    acts = " ".join(summary.get("actions_taken") or [])
    for se in side_effects:
        sid = se.get("id")
        if sid and sid not in acts:
            problems.append(f"actions_taken does not mention {sid}")
    if problems:
        raise HandoffError(problems)
    return render_brief(summary, from_agent, to_agent)


def render_unchecked(summary: dict, original_task: str, side_effects: list[dict], *,
                     from_agent: str = "agent", to_agent: str = "agent") -> str:
    """No checks at all: whatever the transferring agent wrote is what the next agent gets."""
    return render_brief(summary, from_agent, to_agent)


HANDOFF_NOTE = (
    "\n\nYou work in a chain of agents without a supervisor. If part of the request belongs to another specialist, "
    "first finish your own part, then call transfer_to_<name> ONCE. Its arguments are the ONLY thing the next agent "
    "will see: copy the original request verbatim, state its goal, list every fact you found with its source "
    "(include your own answer as a fact), list every request you filed with its id in actions_taken, and copy every "
    "constraint ('do not file ...') word for word. If nothing is left for other agents, answer the user yourself and "
    "include the facts that were handed to you. Other specialists: {others}.")

TRIAGE_SYSTEM = (
    "You are the triage agent of Acme's Company Brain. You never answer questions yourself. Decide which "
    "specialist owns the FIRST part of the request and call its transfer_to_<name> tool with a summary (original "
    "request verbatim, goal, constraints word for word). Specialists:\n"
    + "\n".join(f"- {d}: {DOMAIN_INFO[d]}" for d in DOMAINS)
    + "\nIf the request is too vague to route, ask the user one clarifying question instead of transferring.")


def handoff_policy(history: list[StepRecord], budget: Budget) -> StopDecision:
    """Stop the current agent right after a SUCCESSFUL transfer call; otherwise the normal policy."""
    if history:
        last = history[-1]
        for name, h in zip(last.calls, last.result_hashes):
            if name.startswith("transfer_to_") and h is not None:
                return StopDecision(True, "handoff", name[len("transfer_to_"):])
    return should_stop(history, budget)


@dataclass
class HandoffRunner:
    llm_for: Callable[[str], object]  # role ("triage" | domain) -> llm (the same model for all, or fakes per role)
    requests_db: object = None
    confirm: Optional[Callable] = None
    faults: Optional[dict] = None
    brief: Callable[..., str] = make_handoff_brief  # mine.make_handoff_brief, or render_unchecked
    max_handoffs: int = 4
    budget: Budget = field(default_factory=lambda: Budget(max_steps=8, max_cost_usd=0.02, max_seconds=120))

    def _agent(self, role: str, state: dict) -> Agent:
        others = [d for d in DOMAINS if d != role]
        if role == "triage":
            reg, system = Registry(), TRIAGE_SYSTEM
        else:
            base = specialist_registry(role, self.requests_db, self.faults)
            reg = Registry(dict(base.specs))
            if "create_access_request" in reg.specs:  # remember side effects for the summary check
                spec = reg.specs["create_access_request"]

                def create(a, _fn=spec.fn):
                    out = _fn(a)
                    state["side_effects"].append(out if isinstance(out, dict) else {})
                    return out
                reg.specs["create_access_request"] = ToolSpec(spec.name, spec.description, spec.input_model, create,
                                                              side_effect=True)
            system = SPECIALISTS[role].system + HANDOFF_NOTE.format(
                others=", ".join(f"{d} ({DOMAIN_INFO[d]})" for d in others))

        def transfer(target: str):
            def fn(a: HandoffSummary) -> dict:
                if state["count"] >= self.max_handoffs:
                    raise ToolError(f"Handoff limit ({self.max_handoffs}) reached: answer the user with what you have.")
                try:
                    text = self.brief(a.model_dump(), state["task"], list(state["side_effects"]),
                                      from_agent=role, to_agent=target)
                except HandoffError as exc:
                    state["rejected"].append({"from": role, "to": target, "problems": exc.problems})
                    raise ToolError("Handoff rejected, nothing was transferred. Fix the summary and call the tool "
                                    "again:\n" + "\n".join(f"- {p}" for p in exc.problems))
                state["pending"] = (target, text)
                return {"transferred_to": target, "status": "ok"}
            return fn

        for d in others:
            reg.register(ToolSpec(f"transfer_to_{d}", f"Hand the conversation to the {d} specialist ({DOMAIN_INFO[d]}). "
                                  "The arguments are everything it will see.", HandoffSummary, transfer(d)))
        return Agent(self.llm_for(role), reg, system=system, name=role, confirm=self.confirm, budget=self.budget,
                     policy=handoff_policy)

    def run(self, task: str, *, task_id: str = "") -> MultiResult:
        t0 = time.perf_counter()
        state = {"task": task, "side_effects": [], "pending": None, "count": 0, "rejected": [], "chain": ["triage"]}
        role, message, parent = "triage", task, None
        runs = []
        while True:
            state["pending"] = None
            res = self._agent(role, state).run(message, task_id=task_id)
            run = agent_run(role, "coordinator" if role == "triage" else "worker", res, parent, task_id)
            runs.append(run)
            if res.stop_reason == "handoff" and state["pending"]:
                target, brief = state["pending"]
                state["count"] += 1
                state["chain"].append(target)
                role, message, parent = target, brief, run.run_id
                continue
            info = {"chain": state["chain"], "handoffs": state["count"], "rejected": state["rejected"]}
            return MultiResult("handoff", res.text, res.stop_reason, runs, time.perf_counter() - t0, task_id, info)
