"""Pattern 2: the supervisor (orchestrator-workers). Delegation is a TOOL CALL.

The supervisor is an ordinary agentkit Agent whose only tools are delegate_to_<worker>.
Calling one runs that worker, a separate Agent with its own system prompt, its own tools and
a FRESH context that contains only the `task` (and optional `context`) the supervisor wrote.
The worker's whole trajectory stays inside the worker; the supervisor gets back a short
result: the answer, and (if enabled) the evidence and warnings.

    sup = Supervisor(llm, make_worker=lambda d: make_specialist(d, llm, ...), verify="code")
    res = sup.run("Which rotation covers flow-scheduler? Dana Levi needs admin on kubernetes-prod ...")
    res.text, res.runs  # the answer, and every agent's trajectory (supervisor + workers)

Several delegate calls in ONE turn run in parallel (toolkit's Executor runs read-only calls
concurrently), so independent parts of a request cost the time of the slowest worker.

verify (what protects the supervisor from a worker that returns wrong information):
  "none"  the supervisor sees only the worker's answer and has to trust it
  "llm"   the result also carries `evidence` (the raw tool results the worker saw), and the
          supervisor is told to cross-check names, routes and ids before using an answer
  "code"  multikit compares the answer with the evidence itself (evidence_conflicts) and
          adds `warnings`; deterministic checks beat asking a model to notice
A worker that read a WRONG source (a stale document) produces consistent evidence and a
consistent wrong answer: no verify mode catches that. Only evaluation against gold does.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Optional

from pydantic import BaseModel, Field

from agentkit import Agent, Budget
from toolkit import Registry, ToolSpec

from .attribution import AgentRun, MultiResult, agent_run, annotate
from .domains import DOMAIN_INFO, DOMAINS
from .faults import corrupt_text

ROUTES = ("auto_approve", "needs_manager", "needs_security")


class DelegateInput(BaseModel):
    task: str = Field(description="A self-contained instruction for the worker: the exact part of the user's request "
                                  "it must handle, with every name, system, service and constraint it needs (for "
                                  "example 'do not file anything'). The worker sees NOTHING else.")
    context: Optional[str] = Field(description="Facts from other workers that this worker needs, or a correction "
                                               "note when you ask again; null if none.")


SUPERVISOR_SYSTEM = (
    "You are the supervisor of Acme's Company Brain. You do not have domain tools; you have specialist workers, "
    "each called with a delegate_to_<name> tool:\n{workers}\n"
    "Split the user's request into the parts each worker owns and delegate each part with a self-contained task "
    "(the worker sees only what you write: copy names, systems, services and constraints such as 'do not file' "
    "word for word). Delegate independent parts in the same turn so they run in parallel. Do not delegate a part "
    "that no worker owns, and do not call a worker twice for the same thing unless its answer was wrong or "
    "incomplete. When all parts are answered, reply to the user with one combined answer that keeps every fact, "
    "name, number and request id the workers reported. Never add facts the workers did not report. If the request "
    "is too vague to delegate, ask the user one clarifying question instead.")

VERIFY_LLM = (
    " Each worker result includes `evidence`: the raw tool results the worker saw. Before you use an answer, check "
    "that its key facts (approval routes, names, request ids, numbers) match that evidence. If they do not, delegate "
    "again ONCE with a correction note in `context`; if the answer is still wrong, report the evidence value and "
    "say that the worker's answer conflicted with it.")
VERIFY_CODE = (
    " A worker result may include `warnings`: conflicts between the worker's answer and its own tool results, "
    "found by code. Treat a warning as an error: delegate again ONCE with the warning in `context`; if it is still "
    "there, report the evidence value and mention the conflict.")


@lru_cache(maxsize=1)
def _catalog_names() -> tuple[set[str], set[str]]:
    """Team leads and rotation names from the Engineering Service Catalog (for evidence checks)."""
    from .specialists import ROOT
    text = (ROOT / "data" / "acme" / "corpus" / "docs" / "eng-service-catalog.md").read_text(encoding="utf-8")
    leads, rots = set(), set()
    for ln in text.splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0] not in ("Service", "---") and not cells[0].startswith("-"):
            leads.add(cells[2])
            rots.update(re.findall(r"[a-z-]+-oncall", cells[4]))
    return leads, rots


def evidence_conflicts(answer: str, evidence: list[dict]) -> list[str]:
    """Deterministic checks: does the answer contradict the worker's own tool results?
    evidence: [{"tool": name, "data": dict}] (successful results only)."""
    import json
    low = answer.lower()
    out: list[str] = []
    leads, rots = _catalog_names()
    for ev in evidence:
        d = ev.get("data")
        if d is None and isinstance(ev.get("result"), str):
            try:
                d = json.loads(ev["result"])
            except ValueError:
                d = None
        if not isinstance(d, dict):
            continue
        tool = ev.get("tool")
        if tool == "check_policy" and d.get("route"):
            said = {r for r in ROUTES if r in low}
            if said and d["route"] not in said:
                out.append(f"answer says {', '.join(sorted(said))} but check_policy returned {d['route']}")
        elif tool == "get_oncall_for_service":
            named = {n for n in leads if n.lower() in low}
            if named and d.get("team_lead") and d["team_lead"] not in named:
                out.append(f"answer names {', '.join(sorted(named))} but the catalog lead of {d.get('service')} "
                           f"is {d['team_lead']}")
            said = {r for r in rots if r in low}
            ok = {d.get("rotation"), d.get("secondary")} - {None}
            if said and ok and not (said & ok):
                out.append(f"answer names rotation {', '.join(sorted(said))} but the catalog says "
                           f"{', '.join(sorted(ok))}")
        elif tool == "create_access_request" and d.get("id"):
            ids = set(re.findall(r"AR-\d+", answer))
            if ids and d["id"] not in ids:
                out.append(f"answer cites {', '.join(sorted(ids))} but the filed request is {d['id']}")
    return out


def evidence_of(records: list[dict], max_chars: int = 400) -> list[dict]:
    """The successful tool results of one worker run, compact (what `evidence` carries)."""
    import json
    out = []
    for r in records:
        if r.get("type") != "step":
            continue
        for c, x in zip(r.get("calls", []), r.get("results", [])):
            if x.get("is_error") or c.get("name") in ("note", "give_up"):
                continue
            text = x.get("text", "")
            try:
                data = json.loads(text)
            except ValueError:
                data = None
            if isinstance(data, dict) and "text" in data:  # documents: keep the id, not the body
                data = {k: v for k, v in data.items() if k != "text"}
            out.append({"tool": c["name"], "data": data if isinstance(data, dict) else None,
                        "result": None if isinstance(data, dict) else text[:max_chars]})
    return out


@dataclass
class Supervisor:
    llm: object
    make_worker: Callable[[str], object]  # domain -> Agent (or another Supervisor: hierarchical teams)
    workers: tuple[str, ...] = DOMAINS
    descriptions: dict[str, str] = field(default_factory=lambda: dict(DOMAIN_INFO))
    verify: str = "none"  # none | llm | code
    worker_faults: dict[str, list] = field(default_factory=dict)  # domain -> [(old, new), ...] answer corruption
    fault_times: Optional[int] = None  # corrupt only the first N runs of a faulty worker (None = always)
    budget: Budget = field(default_factory=lambda: Budget(max_steps=6, max_cost_usd=0.03, max_seconds=300))
    name: str = "supervisor"
    max_tokens: int = 1024

    def _system(self) -> str:
        ws = "\n".join(f"- delegate_to_{w}: {self.descriptions.get(w, w)}" for w in self.workers)
        extra = VERIFY_LLM if self.verify == "llm" else VERIFY_CODE if self.verify == "code" else ""
        return SUPERVISOR_SYSTEM.format(workers=ws) + extra

    def run(self, task: str, *, task_id: str = "") -> MultiResult:
        t0 = time.perf_counter()
        lock = threading.Lock()
        children: list[AgentRun] = []
        calls_per_worker: dict[str, int] = {}
        caught: list[dict] = []

        def delegate(domain: str):
            def fn(a: DelegateInput) -> dict:
                brief = a.task + (f"\n\nContext from the supervisor: {a.context}" if a.context else "")
                res = self.make_worker(domain).run(brief, task_id=task_id)
                with lock:
                    n = calls_per_worker[domain] = calls_per_worker.get(domain, 0) + 1
                if isinstance(res, MultiResult):  # a team lead (hierarchical): keep its whole subtree
                    sub_root = res.runs[0] if res.runs else None
                    with lock:
                        for r in res.runs:
                            if r is sub_root:
                                annotate(r.records, role="coordinator", parent_run_id=None, task_id=task_id)
                            children.append(r)
                    text, stop, records = res.text, res.stop_reason, res.records
                else:
                    text, stop, records = res.text, res.stop_reason, res.records
                    with lock:
                        children.append(agent_run(domain, "worker", res, None, task_id))
                rules = self.worker_faults.get(domain)
                if rules and (self.fault_times is None or n <= self.fault_times):
                    text = corrupt_text(text, rules)
                out = {"agent": domain, "answer": text, "stop_reason": stop}
                ev = evidence_of(records)
                if self.verify == "llm":
                    out["evidence"] = ev
                if self.verify == "code":
                    w = evidence_conflicts(text, ev)
                    if w:
                        out["warnings"] = w
                        with lock:
                            caught.append({"agent": domain, "warnings": w})
                return out
            return fn

        reg = Registry()
        for w in self.workers:
            reg.register(ToolSpec(f"delegate_to_{w}", f"Delegate a part of the request to the {w} specialist: "
                                  f"{self.descriptions.get(w, w)}. Returns its answer.", DelegateInput, delegate(w),
                                  timeout_s=300))
        sup = Agent(self.llm, reg, system=self._system(), name=self.name, budget=self.budget,
                    max_tokens=self.max_tokens, tool_timeout_s=300)
        res = sup.run(task, task_id=task_id)
        root = agent_run(self.name, "coordinator", res, None, task_id)
        for c in children:
            head = c.records[0] if c.records else {}
            if head.get("parent_run_id") is None:
                head["parent_run_id"] = root.run_id
        info = {"delegations": dict(calls_per_worker), "warnings": caught}
        return MultiResult("supervisor", res.text, res.stop_reason, [root] + children, time.perf_counter() - t0,
                           task_id, info)
