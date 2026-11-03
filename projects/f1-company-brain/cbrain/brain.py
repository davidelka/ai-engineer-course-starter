"""Brain: the one object the HTTP API, the MCP server, the CLI and the evaluation all use.

    brain = Brain.from_env()
    dana = brain.users["dana"]
    res = brain.ask(dana, "Who approves a Figma editor seat?")           # collected events
    pv = brain.preview(dana, "I need a Figma editor seat")             # what WOULD be filed + token
    st = brain.file_request(dana, pv["text"], pv["confirm_token"])     # starts the workflow
    brain.requests.inbox(brain.users["michal"])                        # Michal's approvals
    brain.requests.decide(st["thread_id"], brain.users["michal"], "approve", "ok")

The paths, and the least-privilege tool set of each:
    knowledge / data   acmeqa retrieval and text-to-SQL (read-only SQL over acme.db): NO tools that
                       change anything. An injected instruction has nothing to call.
    access_request     the ask path never acts: it returns a preview and a single-use confirmation
                       token (toolkit.ConfirmationGate, bound to the exact requester + text). Only an
                       explicit "file it" with that token starts the workflow, whose tools are
                       toolkit's Acme tools, with create_access_request the only side effect.
    approvals          the decision of a human, validated by flowkit against the directory.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Iterator, Optional

from llmkit.types import ToolCall

from .auth import KeyRing, Principal, load_users
from .config import BrainSettings
from .guards import Screens
from .hooks import pick_hooks
from .knowledge import GuardedKnowledge
from .obs import child_span, root_span
from .router import ACCESS_WORD_RE, IntentRouter
from .workflow import AccessRequests

HANDOFF_TEXT = ("This looks like an access request. I have not filed anything: check the preview below and "
                "confirm to start the approval workflow.")


class Brain:
    def __init__(self, s: Optional[BrainSettings] = None):
        from toolkit import ConfirmationGate
        self.s = s or BrainSettings.from_env()
        self.started = time.time()
        self.hooks = pick_hooks(self.s.reference)
        self.users = load_users(self.s.users_file)
        self.keys = KeyRing.from_env(self.users, demo=self.s.demo_keys)
        self.screens = Screens()
        self.gateway = None
        llms = self._models()
        self.llms = llms
        self.knowledge = GuardedKnowledge(self.s, llms["answer"], data_llm=llms.get("data"),
                                          classify=self.hooks.request_classification, screens=self.screens,
                                          tracing=self.s.tracing)
        tr = self.knowledge.tracing
        self.tracer = tr.tracer if tr is not None else None
        if tr is not None and self.s.otlp_endpoint:
            # Phoenix / an OpenTelemetry collector, with the same PII redaction as the JSONL file
            from obskit.redact import RedactingSpanProcessor
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            tr.provider.add_span_processor(RedactingSpanProcessor(BatchSpanProcessor(
                OTLPSpanExporter(endpoint=self.s.otlp_endpoint.rstrip("/") + "/v1/traces"))))
        router_llm = llms["router"]
        if self.tracer is not None:
            from obskit import InstrumentedLLM
            router_llm = InstrumentedLLM(router_llm, tracer=self.tracer, prompt_name="router", prompt_version="f1-v1")
        self.router = IntentRouter(router_llm, rules=self.hooks.rule_intent, llm_mode=self.s.router_llm)
        self.requests = AccessRequests(self.s, llms["flow"], hooks=self.hooks, screens=self.screens,
                                       tracer=self.tracer)
        self.confirm = ConfirmationGate(ttl_s=900)

    @classmethod
    def from_env(cls, **overrides: Any) -> "Brain":
        return cls(BrainSettings.from_env(**overrides))

    def _models(self) -> dict:
        from . import models
        s = self.s
        if s.llm_path == "gateway":
            from .gateway import gateway_llms
            upstream = None
            if s.mode == "sim":
                upstream = models.OfflineUpstream(answer=models.ObedientChat())
            llms, self.gateway = gateway_llms(s, upstream)
            out = {"answer": llms["answer"], "flow": llms["flow"], "router": llms["router"]}
            if s.mode == "live":
                out["data"] = llms["answer"]
            return out
        return {"answer": models.answer_llm(s), "flow": models.flow_llm(s), "router": models.router_llm(s)}

    # ------------------------------------------------------------ ask
    def ask_events(self, p: Principal, question: str, *, extra_hits: Optional[list] = None,
                   _sink: Optional[dict] = None) -> Iterator[dict]:
        """Events of one /ask. Iterate it in ONE thread (service.py does)."""
        question = (question or "").strip()
        with root_span(self.tracer, "ask", p, question_chars=len(question)) as root:
            with child_span(self.tracer, "intent_route") as sp:
                r = self.router.route(question)
                if sp is not None:
                    sp.set_attribute("brain.intent", r.intent)
                    sp.set_attribute("brain.route_source", r.source)
            if root is not None:
                root.set_attribute("brain.intent", r.intent)
            yield {"event": "intent", "data": r.to_dict()}
            cost = (r.llm or {}).get("cost_usd", 0.0)
            if r.intent == "access_request":
                pv = self.preview(p, question, _span=False)
                cost += pv.get("cost_usd", 0.0)
                yield {"event": "confirm", "data": pv}
                yield {"event": "answer", "data": {"text": HANDOFF_TEXT, "refused": False, "kind": "handoff",
                                                   "citations": [], "invalid_citations": []}}
                yield {"event": "done", "data": {"cost_usd": round(cost, 6), "usage": {}, "latency_ms": None,
                                                 "ttft_ms": None, "timings_ms": {}, "trace_id": _tid(root),
                                                 "model": "-"}}
                if root is not None:
                    root.set_attribute("obskit.cost_usd", round(cost, 8))
                return
            for ev in self.knowledge.events(question, p.acl_role, extra_hits=extra_hits, _sink=_sink):
                if ev["event"] == "done":
                    ev = {"event": "done", "data": {**ev["data"], "cost_usd": round(ev["data"].get("cost_usd", 0.0)
                                                                                      + cost, 6),
                                                    "brain_trace_id": _tid(root)}}
                yield ev
            if r.source != "rules" or "access_word" in r.matched:
                if ACCESS_WORD_RE.search(question):
                    yield {"event": "suggest", "data": {"action": "preview_access_request", "text": question}}

    def ask(self, p: Principal, question: str, **kw: Any) -> dict:
        out: dict = {"question": question, "events": []}
        tokens: list[str] = []
        for ev in self.ask_events(p, question, **kw):
            e, d = ev["event"], ev["data"]
            out["events"].append(e)
            if e == "token":
                tokens.append(d.get("text", ""))
            elif e in ("intent", "answer", "done", "confirm", "route", "data", "guard", "sources", "suggest", "error"):
                if e == "guard":
                    out.setdefault("guard", []).append(d)
                else:
                    out[e] = d
        out["streamed_text"] = "".join(tokens)
        return out

    # ------------------------------------------------------------ requests
    def _call(self, p: Principal, text: str) -> ToolCall:
        return ToolCall(id=f"ask-{p.id}", name="start_access_request", arguments={"requester": p.email, "text": text})

    def preview(self, p: Principal, text: str, *, _span: bool = True) -> dict:
        """What filing this text WOULD do (intake extraction + directory + policy), without filing.
        Returns the preview and a single-use confirmation token for exactly this requester + text."""
        from contextlib import nullcontext

        from flowkit.fake import SYSTEMS
        from flowkit.nodes import INTAKE_SYSTEM, call_tool
        from flowkit.state import IntakeRequest
        from llmkit.structured import StructuredError, complete_structured
        from toolkit.registry import ToolError
        cm = root_span(self.tracer, "request", p, step="preview") if _span else nullcontext(None)
        with cm:
            out: dict = {"action": "start_access_request", "text": text, "cost_usd": 0.0}
            try:
                res = complete_structured(self.requests.deps.llm, f"Sender: {p.email}\n<request>\n{text}\n</request>",
                                          IntakeRequest, max_repairs=1, max_tokens=400,
                                          system=INTAKE_SYSTEM.format(systems=", ".join(SYSTEMS)))
                req = res.value.model_dump()
                out["cost_usd"] = res.cost_usd or 0.0
                emp = call_tool(self.requests.deps, "lookup_employee", {"employee": req.get("employee") or p.email})
                info = call_tool(self.requests.deps, "get_system_info", {"system": req["system"]})
                pol = call_tool(self.requests.deps, "check_policy", {
                    "system": info["name"], "access_level": req["access_level"],
                    "external_sharing": bool(req.get("external_sharing")), "holds_customer_or_financial_data": None})
                v = self.screens.question(text)
                pol = self.hooks.harden_route(pol, list(v.reasons) if v.flagged else [])
                approver = {"auto_approve": "granted immediately", "needs_manager":
                            f"your manager decides ({(emp.get('manager') or {}).get('name', '?')})",
                            "needs_security": "the security team decides (2 business days; expires after 90 days)"}
                out.update(employee=f"{emp['name']} ({emp['id']})", system=info["name"],
                           access_level=req["access_level"], duration_days=req.get("duration_days"),
                           justification=req.get("justification"), route=pol["route"],
                           approver=approver.get(pol["route"], "?"), reasons=pol.get("reasons", []),
                           hardened=bool(pol.get("hardened")))
            except (StructuredError, ToolError, Exception) as exc:  # noqa: BLE001  (a preview never fails the request)
                out["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            out["confirm_token"] = self.confirm.approve(self._call(p, text))
            return out

    def check_token(self, p: Principal, text: str, token: Optional[str]) -> bool:
        return self.confirm.check(self._call(p, text), token)

    def file_request_events(self, p: Principal, text: str, token: Optional[str]) -> Iterator[dict]:
        if not self.check_token(p, text, token):
            raise PermissionError("missing, expired, reused or mismatched confirmation token: preview the request "
                                  "again and confirm the preview you saw")
        with root_span(self.tracer, "request", p, step="start") as root:
            for ev in self.requests.start(p, text):
                if ev["event"] == "summary" and root is not None:
                    root.set_attribute("brain.thread_id", ev["data"]["thread_id"])
                    root.set_attribute("brain.status", ev["data"]["status"] or "")
                    root.set_attribute("obskit.cost_usd", float((ev["data"].get("usage") or {}).get("cost_usd", 0.0)))
                yield ev

    def file_request(self, p: Principal, text: str, token: Optional[str]) -> dict:
        summary = None
        for ev in self.file_request_events(p, text, token):
            if ev["event"] == "summary":
                summary = ev["data"]
        return summary or {}

    def start_request_unconfirmed(self, p: Principal, text: str) -> dict:
        """For the evaluation and the seed script ONLY (they are the human). The API never calls this."""
        token = self.confirm.approve(self._call(p, text))
        return self.file_request(p, text, token)

    def decide(self, p: Principal, tid: str, decision: str, comment: str = "") -> dict:
        with root_span(self.tracer, "decide", p, thread_id=tid, decision=decision) as root:
            res = self.requests.decide(tid, p, decision, comment)
            if root is not None:
                root.set_attribute("brain.ok", bool(res["ok"]))
            return res

    # ------------------------------------------------------------ ops
    def spans(self) -> list[dict]:
        tr = self.knowledge.tracing
        if tr is None or tr.memory is None:
            return []
        tr.flush()
        return list(tr.memory.spans)

    def ready(self) -> dict:
        checks = {}
        try:
            checks["index"] = len(self.knowledge.assistant.job.all_chunks()) > 0
        except Exception:  # noqa: BLE001
            checks["index"] = False
        try:
            self.requests.threads()
            checks["state"] = True
        except Exception:  # noqa: BLE001
            checks["state"] = False
        checks["users"] = len(self.users) > 0
        checks["keys"] = len(self.keys) > 0
        return {"ready": all(checks.values()), "checks": checks, "settings": self.s.describe(),
                "using": self.hooks.using}

    def close(self) -> None:
        self.knowledge.assistant.close()


def _tid(root) -> str:
    if root is None:
        return ""
    return format(root.get_span_context().trace_id, "032x")


def principal_for_role(acl_role: str, employee_id: Optional[str] = None) -> Principal:
    """A synthetic employee with a given document role (security evaluation, CLI)."""
    return Principal(id=f"eval-{acl_role}", email=f"{acl_role}.user@acme.example", name=f"eval {acl_role}",
                     employee_id=employee_id, roles=frozenset({"employee"}), acl_role=acl_role)


def new_thread_id() -> str:
    return f"req-{uuid.uuid4().hex[:10]}"
