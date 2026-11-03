"""Pattern 1: the router. Classify once, then hand the whole request to ONE specialist.

    decision = classify(llm, task)                   # one structured-output call (llmkit.structured)
    choice = decide_route(decision, threshold=0.6)   # code, not the model, makes the final call
    -> "route": run the specialist(s) on the request
    -> "clarify": ask the user a question instead of guessing

The router is the cheapest multi-agent pattern: one small classification call (a few
hundred tokens), then a specialist with a short prompt and 2-6 tools instead of one agent
with all 10. Its weakness is structural: it decides ONCE, up front. A request that spans two
domains either goes to one specialist (who answers half of it) or, with max_targets=2, to two
specialists who each answer their half, glued together without any model reading both.

decide_route() is the reference for lesson 18, exercise 2 (mine.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

from pydantic import BaseModel, Field

from llmkit.structured import StructuredError, complete_structured

from .attribution import MultiResult, agent_run, llm_call_records
from .domains import DOMAIN_INFO, DOMAINS

Route = Literal["hr", "it_access", "oncall"]


class RouteDecision(BaseModel):
    reason: str = Field(description="One sentence: which parts of the request belong to which domain, and why")
    routes: list[Route] = Field(description="The domains the request needs, most important first; [] if none fits "
                                            "or the request is too vague to tell")
    confidence: float = Field(ge=0.0, le=1.0, description="How sure you are that `routes` is right, 0.0 to 1.0")
    clarifying_question: Optional[str] = Field(description="If the request is ambiguous: ONE short question to ask "
                                                           "the user; otherwise null")


ROUTER_SYSTEM = (
    "You are the router of Acme's Company Brain. You do not answer questions: you decide which specialist "
    "agent(s) should handle a request. The specialists:\n"
    + "\n".join(f"- {d}: {DOMAIN_INFO[d]}" for d in DOMAINS)
    + "\nReturn every domain the request needs (most important first). If the request is too vague to route "
      "(no clear person, system, service or policy), return no routes, a low confidence and one clarifying "
      "question. Be honest about confidence: 0.9+ only when one domain clearly fits.")

DEFAULT_QUESTION = ("Could you say a bit more? I can help with HR policies, access to systems, or on-call information "
                    "for a production service.")


@dataclass
class RouteChoice:
    action: str  # "route" | "clarify"
    targets: list[str] = field(default_factory=list)
    question: Optional[str] = None
    why: str = ""


def decide_route(decision: RouteDecision, *, threshold: float = 0.6, allowed: tuple[str, ...] = DOMAINS,
                 max_targets: int = 1) -> RouteChoice:
    """See labs/18-multi-agent/mine.py for the exact contract (this is the reference)."""
    targets = [r for r in dict.fromkeys(decision.routes) if r in allowed][:max_targets]
    question = decision.clarifying_question if (decision.clarifying_question or "").strip() else DEFAULT_QUESTION
    if not targets:
        return RouteChoice("clarify", [], question, "no allowed route")
    if decision.confidence < threshold:
        return RouteChoice("clarify", [], question, f"confidence {decision.confidence:.2f} < {threshold:.2f}")
    return RouteChoice("route", targets, None, f"confidence {decision.confidence:.2f} >= {threshold:.2f}")


def classify(llm, task: str, *, max_tokens: int = 300):
    """One structured call. Returns llmkit StructuredResult (value = RouteDecision, tokens, cost, latency)."""
    prompt = f"Route this request.\n<task>\n{task}\n</task>"
    return complete_structured(llm, prompt, RouteDecision, system=ROUTER_SYSTEM, max_tokens=max_tokens)


@dataclass
class Router:
    """make_worker(domain) -> agentkit Agent (a fresh specialist for each request)."""

    router_llm: object
    make_worker: Callable[[str], object]
    threshold: float = 0.6
    max_targets: int = 1
    decide: Callable[..., RouteChoice] = decide_route  # swap in mine.decide_route for the lab

    def run(self, task: str, *, task_id: str = "") -> MultiResult:
        t0 = time.perf_counter()
        t0_ms = time.time() * 1000
        try:
            sr = classify(self.router_llm, task)
            dec: RouteDecision = sr.value
        except StructuredError as exc:  # refusal / truncated / invalid after repairs: ask, never guess
            sr = exc.result
            dec = RouteDecision(reason=f"router failed: {exc.stage}", routes=[], confidence=0.0,
                                clarifying_question=None)
        head = llm_call_records("router", "coordinator", input_tokens=sr.input_tokens, output_tokens=sr.output_tokens,
                                cost_usd=sr.cost_usd, elapsed_s=sr.latency_s, text=dec.model_dump_json(),
                                model=getattr(self.router_llm, "model", "?"), task_id=task_id, t0_ms=t0_ms,
                                estimated=bool(getattr(self.router_llm, "estimated", False)), calls=sr.attempts)
        runs = [_run("router", "coordinator", head)]
        choice = self.decide(dec, threshold=self.threshold, max_targets=self.max_targets)
        info = {"decision": dec.model_dump(), "choice": choice.__dict__}  # a clarifying question is a normal end
        if choice.action == "clarify":
            return MultiResult("router", choice.question or DEFAULT_QUESTION, "final_answer", runs,
                               time.perf_counter() - t0, task_id, info)
        texts, stops = [], []
        for d in choice.targets:
            res = self.make_worker(d).run(task, task_id=task_id)
            runs.append(agent_run(d, "worker", res, head[0]["run_id"], task_id))
            texts.append(res.text)
            stops.append(res.stop_reason)
        # several specialists: their answers are concatenated; no model reads them together
        stop = stops[0] if len(set(stops)) == 1 else ("final_answer" if all(s in ("final_answer", "gave_up") for s in stops) else stops[-1])
        return MultiResult("router", "\n\n".join(texts), stop, runs, time.perf_counter() - t0, task_id, info)


def _run(name, role, records):
    from .attribution import AgentRun
    return AgentRun(name, role, records, None, records[-1].get("text", ""), "final_answer")
