"""The same job as a FIXED workflow (lesson 15, exercise 8; lesson 16 builds this in LangGraph).

When the steps are known in advance, you do not need a model to choose them:

    extract fields -> lookup_employee -> list_access_grants (if asked) -> check_policy
                   -> decide in code -> create_access_request (human confirms) -> answer

At most ONE model call (field extraction, with structured output; or a regex parser
offline), a fixed number of tool calls, no loop, nothing to budget. The price: it only
handles the shape it was built for. A question outside that shape ("compare two
systems", "what does the document say") gets "unsupported", where an agent would adapt.

The workflow writes the same trajectory records as the Agent (run, step, confirm, stop),
so the same evaluator scores both.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Callable, Literal, Optional

from pydantic import BaseModel, Field

from llmkit.structured import StructuredError, complete_structured
from llmkit.types import ToolCall, ToolResult
from toolkit.confirm import ConfirmationGate
from toolkit.executor import execute_tool
from toolkit.registry import Registry

from .fake import parse_task
from .policy import fingerprint, result_hash
from .trajectory import TrajectoryLog
from .types import AgentResult

Level = Literal["read", "viewer", "member", "editor", "write", "admin", "owner"]


class AccessAsk(BaseModel):
    supported: bool = Field(description="true only if the message is about access for ONE named person to ONE system "
                                        "(a request to file, a route question, or an existing-access check)")
    employee: Optional[str] = Field(description="Work email, employee id or name as written, or null")
    system: Optional[str] = Field(description="System name lowercase with dashes, e.g. 'aws-production', or null")
    access_level: Level = Field(description="Requested level; 'member' if not stated")
    duration_days: Optional[int] = Field(description="Requested duration in days, or null")
    wants_request: bool = Field(description="true if the user asked to file/open/submit a request")
    only_if_auto: bool = Field(description="true if the user said to file only when it can be auto-approved")
    check_existing: bool = Field(description="true if the user asked whether the person already has this access")
    external_sharing: bool = Field(description="true for sharing data externally or connecting an OAuth app")


def extract_offline(task: str) -> AccessAsk:
    s = parse_task(task)
    supported = bool(s.employee and s.system and not s.compare and not s.list_access and not s.wants_doc)
    return AccessAsk(supported=supported, employee=s.employee, system=s.system, access_level=s.level,
                     duration_days=s.duration, wants_request=s.wants_request, only_if_auto=s.only_if_auto,
                     check_existing=s.check_grants, external_sharing=s.external)


def run_workflow(task: str, registry: Registry, *, confirm: Optional[Callable[[ToolCall], bool]] = None,
                 llm=None, log_path: Optional[str] = None, task_id: str = "") -> AgentResult:
    t0 = time.perf_counter()
    log = TrajectoryLog(log_path, uuid.uuid4().hex[:16])
    out = AgentResult(text="", stop_reason="final_answer", estimated_cost=bool(getattr(llm, "estimated", False)))
    log.write({"type": "run", "agent": "access_workflow", "task_id": task_id, "task": task,
               "model": getattr(llm, "model", "none (regex extraction)"), "mode": "workflow",
               "budget": {"max_steps": "fixed"}, "tools": registry.names()})
    gate = ConfirmationGate()
    n = 0

    def call(name: str, args: dict) -> ToolResult:
        nonlocal n
        n += 1
        c = ToolCall(f"wf_{n}", name, args, json.dumps(args))
        spec = registry.get(name)
        if spec is not None and spec.side_effect:
            approved = bool(confirm and confirm(c))
            log.write({"type": "confirm", "n": n, "call": {"name": name, "arguments": args}, "approved": approved,
                       "tainted": False})
            if approved:
                gate.approve(c)
        ts = time.time() * 1000
        r = execute_tool(c, registry, confirmed=gate.confirmed)
        te = time.time() * 1000
        out.calls.append(c)
        out.results.append(r)
        side = bool(spec and spec.side_effect)
        log.write({"type": "step", "n": n, "t_start": round(ts, 1), "t_model_end": round(ts, 1), "thought": "",
                   "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                   "calls": [{"id": c.id, "name": name, "arguments": args, "fp": fingerprint(c)}],
                   "results": [{"id": c.id, "name": name, "is_error": r.is_error, "hash": result_hash(r),
                                "text": r.text if side else r.text[:600], "chars": len(r.text), "side_effect": side,
                                "t_start": round(ts, 1), "t_end": round(te, 1)}],
                   "cum_cost_usd": out.cost_usd, "decision": {"reason": "continue", "detail": "fixed workflow"}})
        return r

    def finish(text: str, reason: str = "final_answer", detail: str = "") -> AgentResult:
        out.text, out.stop_reason, out.detail = text, reason, detail
        out.steps = n
        out.elapsed_s = time.perf_counter() - t0
        log.write({"type": "stop", "task_id": task_id, "reason": reason, "detail": detail, "steps": n,
                   "tool_calls": len(out.calls), "errors": out.errors, "input_tokens": out.input_tokens,
                   "output_tokens": out.output_tokens, "cost_usd": out.cost_usd,
                   "estimated_cost": out.estimated_cost, "elapsed_s": round(out.elapsed_s, 3), "text": text})
        out.records = log.records
        return out

    # 1. extract (one model call, or regexes)
    if llm is not None:
        try:
            sr = complete_structured(llm, f"Extract the fields from this message to Acme's access desk:\n<message>\n"
                                          f"{task}\n</message>", AccessAsk, max_repairs=1)
            ask = sr.value
            out.input_tokens, out.output_tokens, out.cost_usd = sr.input_tokens, sr.output_tokens, sr.cost_usd
        except StructuredError as exc:
            return finish(f"Could not read the request: {exc}", "model_error", str(exc)[:200])
    else:
        ask = extract_offline(task)
    if not ask.supported or not ask.employee or not ask.system:  # type: ignore[union-attr]
        return finish("This workflow only handles access for one person and one system; this request needs a "
                      "person (or an agent).", "unsupported", "outside the workflow's shape")

    # 2. who
    emp = call("lookup_employee", {"employee": ask.employee})
    if emp.is_error:
        return finish(emp.text)
    e = json.loads(emp.text)
    mgr = e.get("manager") or {}
    facts = [f"{e['name']} ({e['id']}) reports to {mgr.get('name', 'nobody')} ({mgr.get('id', '-')})."]

    # 3. existing access
    if ask.check_existing:
        g = call("list_access_grants", {"employee": e["email"], "system": ask.system, "include_expired": False})
        if not g.is_error:
            have = [x for x in json.loads(g.text).get("grants", []) if x["level"] == ask.access_level
                    or ask.access_level == "member"]
            if have:
                return finish(" ".join(facts + [f"They already have {ask.system} {have[0]['level']} access "
                                                f"({have[0]['id']}); nothing was filed."]))
            facts.append(f"No current {ask.system} grant at that level.")

    # 4. policy
    p = call("check_policy", {"system": ask.system, "access_level": ask.access_level,
                              "external_sharing": ask.external_sharing, "holds_customer_or_financial_data": None})
    if p.is_error:
        return finish(" ".join(facts + [p.text]))
    pol = json.loads(p.text)
    facts.append(f"check_policy: {ask.access_level} on {pol['system']} routes to {pol['route']} ({pol['review_target']}).")

    # 5. decide in code, then the side effect behind a human
    if not ask.wants_request:
        return finish(" ".join(facts))
    if ask.only_if_auto and pol["route"] != "auto_approve":
        return finish(" ".join(facts + ["Not filed: it cannot be auto-approved."]))
    r = call("create_access_request", {"employee": e["email"], "system": pol["system"], "access_level": ask.access_level,
                                       "justification": task.split(".")[0][:160], "duration_days": ask.duration_days,
                                       "idempotency_key": f"{e['email']}:{pol['system']}:{ask.access_level}"})
    if r.is_error:
        return finish(" ".join(facts + ["The request was NOT submitted: " + r.text[:160]]))
    c = json.loads(r.text)
    return finish(" ".join(facts + [f"Filed {c['id']}: route {c['route']}, status {c['status']}, approver "
                                    f"{c['approver']}, expires {c.get('expires_at') or 'never'}."]))
