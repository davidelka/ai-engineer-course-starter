"""The access-request path: flowkit's LangGraph workflow (lesson 16), served to many users.

    reqs = AccessRequests(settings, llm, hooks=hooks)
    events = list(reqs.start(dana, "I need a Figma editor seat for the new dashboards"))
    reqs.inbox(michal)                       # [{thread_id, gate: "manager", ...}]
    reqs.decide(tid, michal, "approve", "ok, for Q4")

Nothing about the workflow itself is re-implemented: the graph, the nodes, the approval gates
(interrupt), the SQLite checkpoints, REQ-8..REQ-11 (who may decide, no self-approval, closed stays
closed, every transition audited), idempotent filing and the outbox all come from flowkit. What
this module adds for a multi-user service:

- identity: the requester and the approver are the AUTHENTICATED principal (an email), never a
  value from the request body or the text. flowkit then checks authority against the directory.
- one extension through flowkit's own seam (build_graph(impl=...)): policy_node runs the reference
  check_policy, then harden_route (milestone 5): text that guardkit's detector flags is never
  auto-approved, and the approver sees why.
- an index of threads (brain_threads in requests.db): who filed what, when. LangGraph's
  checkpointer knows threads, not users.
- the approvals inbox (approvals_for, milestone 4) and visibility rules for status/audit.
- traces: the workflow's LLM calls (InstrumentedLLM) and tool calls (tool spans) under the
  request's root span. Tools run in toolkit's thread pool, which does not carry the OpenTelemetry
  context, so TracedRegistry captures the context when flowkit looks the tool up.

State: requests.db (toolkit's access_requests + flowkit's flow_audit/flow_outbox + brain_threads)
and checkpoints.db (LangGraph). Both SQLite, one writer process (ADR-0003 and the Terraform notes on
EFS). A per-process lock serializes graph runs: LangGraph's SqliteSaver shares one connection.
"""

from __future__ import annotations

import contextvars
import json
import sqlite3
import threading
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, Optional

from toolkit import acme_registry
from toolkit.registry import Registry

from .auth import Principal
from .config import BrainSettings

THREADS_SCHEMA = """CREATE TABLE IF NOT EXISTS brain_threads (
  thread_id TEXT PRIMARY KEY, requester TEXT NOT NULL, requester_id TEXT, created_at TEXT NOT NULL,
  text_preview TEXT NOT NULL, flags TEXT NOT NULL DEFAULT '[]')"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- milestone 4 (mine.approvals_for)
def approvals_for(*args, **kwargs):
    """Milestone 4: runs your mine.approvals_for (see cbrain/hooks.py)."""
    from .hooks import call
    return call("approvals_for", *args, **kwargs)


# ---------------------------------------------------------------- tracing helpers
class TracedRegistry(Registry):
    """A Registry whose tools run inside a tool span, in the caller's OpenTelemetry context."""

    def __init__(self, inner: Registry, tracer: Any):
        super().__init__(dict(inner.specs))
        self._tracer = tracer

    def get(self, name: str):
        spec = self.specs.get(name)
        if spec is None or self._tracer is None:
            return spec
        ctx = contextvars.copy_context()          # captured in the calling (graph) thread
        tracer, fn = self._tracer, spec.fn

        def traced(args):
            def run():
                from obskit import tool_span
                with tool_span(name, tracer=tracer, attributes={"acme.side_effect": bool(spec.side_effect)}):
                    return fn(args)
            return ctx.run(run)
        return replace(spec, fn=traced)


def open_saver(path: Path, *, exclusive: bool = False):
    """flowkit.open_checkpointer, plus the EFS option: PRAGMA locking_mode=EXCLUSIVE BEFORE SqliteSaver
    switches the file to WAL, so SQLite never creates the shared-memory wal-index (sqlite.org/wal.html,
    "Use of WAL Without Shared-Memory"). The price: no other process may open checkpoints.db."""
    from langgraph.checkpoint.sqlite import SqliteSaver
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), check_same_thread=False)
    if exclusive:
        con.execute("PRAGMA locking_mode=EXCLUSIVE")
    return SqliteSaver(con)


# ---------------------------------------------------------------- the service object
class AccessRequests:
    def __init__(self, s: BrainSettings, llm: Any, *, hooks: Any, screens: Any = None, tracer: Any = None,
                 registry: Optional[Registry] = None):
        from flowkit import Deps, build_graph
        self.s = s
        self.hooks = hooks
        self.screens = screens
        self.tracer = tracer
        s.state_dir.mkdir(parents=True, exist_ok=True)
        self.db = s.requests_db
        reg = registry or acme_registry(requests_db=self.db)
        self.registry = TracedRegistry(reg, tracer) if tracer is not None else reg
        if tracer is not None:
            from obskit import InstrumentedLLM
            llm = InstrumentedLLM(llm, tracer=tracer, prompt_name="flow", prompt_version="flowkit-16")
        self.deps = Deps(llm=llm, registry=self.registry, requests_db=self.db)
        self.saver = open_saver(s.checkpoints_db, exclusive=s.sqlite_exclusive)
        self.app = build_graph(self.deps, impl=SimpleNamespace(policy_node=self._policy_node),
                               checkpointer=self.saver)
        self.lock = threading.RLock()
        con = self._con()
        con.execute(THREADS_SCHEMA)
        con.commit()
        con.close()

    def _con(self) -> sqlite3.Connection:
        from flowkit import store
        con = store.connect(self.db)
        con.row_factory = sqlite3.Row
        return con

    # flowkit's extension point: policy_node(state, deps) -> partial update
    def _policy_node(self, state: dict, deps: Any) -> dict:
        from flowkit import nodes as ref
        upd = ref.policy_node(state, deps)
        flags: list[str] = []
        if self.screens is not None:
            v = self.screens.question(state.get("text", ""))
            flags = list(v.reasons) if v.flagged else []
        pol = self.hooks.harden_route(upd["policy"], flags)
        if pol.get("hardened"):
            ref.progress("policy", f"route hardened to {pol['route']}: {pol['reasons'][-1]}")
            ev = ref.audit_event(state, deps, to="routed", note=f"{pol['route']} (hardened)",
                                 event_id=f"{state.get('thread_id')}:routed:hardened")
            return {**upd, "policy": pol, "route": pol["route"], "audit": upd.get("audit", []) + [ev]}
        return {**upd, "policy": pol, "route": pol["route"]}

    # ------------------------------------------------------------ start
    def start(self, principal: Principal, text: str, *, thread_id: Optional[str] = None) -> Iterator[dict]:
        """Run the workflow until it ends or pauses at a gate. Yields progress dicts, then a summary."""
        from flowkit import runner
        tid = thread_id or f"req-{uuid.uuid4().hex[:10]}"
        created = utc_now()
        flags: list[str] = []
        if self.screens is not None:
            v = self.screens.question(text)
            flags = list(v.reasons) if v.flagged else []
        con = self._con()
        con.execute("INSERT OR IGNORE INTO brain_threads VALUES (?,?,?,?,?,?)",
                    (tid, principal.email, principal.employee_id, created, text[:160], json.dumps(flags)))
        con.commit()
        con.close()
        yield {"event": "started", "data": {"thread_id": tid, "requester": principal.email, "flags": flags}}
        with self.lock:
            for mode, chunk in runner.start(self.app, tid, principal.email, text, created):
                yield from self._translate(mode, chunk)
        yield {"event": "summary", "data": self.status(tid)}

    @staticmethod
    def _translate(mode: str, chunk: Any) -> Iterator[dict]:
        if mode == "custom":
            yield {"event": "progress", "data": {"node": chunk.get("node"), "msg": chunk.get("msg")}}
            return
        for node, upd in (chunk or {}).items():
            if node == "__interrupt__":
                for i in upd:
                    v = i.value or {}
                    yield {"event": "paused", "data": {"gate": v.get("gate"), "request_id": v.get("request_id"),
                                                       "allowed_approvers": v.get("allowed_approvers", []),
                                                       "previous_error": v.get("previous_error")}}
                continue
            upd = upd or {}
            yield {"event": "step", "data": {"node": node, "status": upd.get("status")}}

    # ------------------------------------------------------------ read side
    def thread_row(self, tid: str) -> Optional[dict]:
        con = self._con()
        try:
            r = con.execute("SELECT * FROM brain_threads WHERE thread_id = ?", (tid,)).fetchone()
            return dict(r) if r else None
        finally:
            con.close()

    def status(self, tid: str) -> dict:
        from flowkit import runner
        with self.lock:
            summ = runner.summary(self.app, tid)
            v = self.app.get_state(runner.config(tid)).values or {}
        row = self.thread_row(tid) or {}
        emp = v.get("employee") or {}
        con = self._con()
        try:
            db_rows = [dict(r) for r in con.execute("SELECT * FROM flow_audit WHERE thread_id = ? ORDER BY at, rowid",
                                                    (tid,))]
        finally:
            con.close()
        # The state's audit list has every transition (REQ-11); the flow_audit table has the ones written
        # next to a side effect (filing, decisions, escalation). Merge by event id, state order first.
        seen, audit = set(), []
        for e in list(v.get("audit") or []) + db_rows:
            if e.get("id") in seen:
                continue
            seen.add(e.get("id"))
            audit.append({k: e.get(k) for k in ("id", "at", "actor", "from_status", "to_status", "note", "request_id")}
                         | {"stored": any(r["id"] == e.get("id") for r in db_rows)})
        req = v.get("request") or {}
        return {
            "thread_id": tid, "status": summ["status"], "done": summ["done"], "paused_at_gate": summ["paused_at_gate"],
            "gate": (summ["gate"] or {}).get("gate"), "gate_error": (v.get("gate_error") or {}).get("message"),
            "route": v.get("route"), "request_id": summ["request_id"], "requester": row.get("requester"),
            "created_at": row.get("created_at"), "text": row.get("text_preview"),
            "flags": json.loads(row.get("flags") or "[]"),
            "request": {k: req.get(k) for k in ("employee", "system", "access_level", "duration_days",
                                                 "justification", "external_sharing")} if req else None,
            "employee": {k: emp.get(k) for k in ("id", "name", "email", "title", "team")} if emp else None,
            "manager": (emp.get("manager") or {}).get("name") if emp else None,
            "reasons": (v.get("policy") or {}).get("reasons", []),
            "hardened": bool((v.get("policy") or {}).get("hardened")),
            "risk_summary": v.get("risk_summary"), "decision": v.get("decision"),
            "notifications": v.get("notifications", []), "error": v.get("error"), "usage": v.get("usage", {}),
            "audit": audit,
        }

    def threads(self, requester: Optional[str] = None) -> list[dict]:
        con = self._con()
        try:
            if requester:
                rows = con.execute("SELECT * FROM brain_threads WHERE requester = ? ORDER BY created_at DESC",
                                   (requester,))
            else:
                rows = con.execute("SELECT * FROM brain_threads ORDER BY created_at DESC")
            return [dict(r) for r in rows]
        finally:
            con.close()

    def pending_items(self) -> list[dict]:
        """Every thread paused at a gate, with the fields approvals_for needs."""
        from flowkit import runner
        out = []
        for row in self.threads():
            with self.lock:
                summ = runner.summary(self.app, row["thread_id"])
                if not summ["paused_at_gate"]:
                    continue
                v = self.app.get_state(runner.config(row["thread_id"])).values or {}
            emp, req, gate = v.get("employee") or {}, v.get("request") or {}, summ["gate"] or {}
            out.append({"thread_id": row["thread_id"], "gate": gate.get("gate"), "request_id": summ["request_id"],
                        "employee_id": emp.get("id"), "employee": emp.get("name"),
                        "requester_id": (v.get("requester_info") or {}).get("id") or row.get("requester_id"),
                        "manager_id": (emp.get("manager") or {}).get("id"), "created_at": row["created_at"],
                        "system": req.get("system"), "access_level": req.get("access_level"),
                        "duration_days": req.get("duration_days"), "justification": req.get("justification"),
                        "reasons": gate.get("reasons", []), "risk_summary": gate.get("risk_summary"),
                        "previous_error": gate.get("previous_error"), "flags": json.loads(row.get("flags") or "[]")})
        return out

    def inbox(self, principal: Principal) -> list[dict]:
        return self.hooks.approvals_for(principal, self.pending_items())

    def can_view(self, principal: Principal, tid: str) -> bool:
        row = self.thread_row(tid)
        if row is None:
            return False
        if principal.has("admin", "security") or row["requester"] == principal.email:
            return True
        st = self.status(tid)
        emp = st.get("employee") or {}
        if emp.get("id") and emp.get("id") == principal.employee_id:
            return True
        return any(it["thread_id"] == tid for it in self.inbox(principal)) or any(
            e.get("actor") == principal.employee_id for e in st["audit"])

    # ------------------------------------------------------------ decide
    def decide(self, tid: str, principal: Principal, decision: str, comment: str = "") -> dict:
        """Resume the paused workflow with this principal's decision. flowkit validates authority
        (REQ-8/REQ-9) against the directory; a refused answer leaves the thread paused, with the
        reason in gate_error."""
        from flowkit import runner
        if decision not in ("approve", "reject"):
            raise ValueError("decision must be approve or reject")
        events = []
        with self.lock:
            summ = runner.summary(self.app, tid)
            if not summ["paused_at_gate"]:
                return {"ok": False, "error": f"request {tid} is not waiting for a decision (status "
                                              f"{summ['status']})", "events": [], "summary": self.status(tid)}
            answer = {"decision": decision, "actor": principal.email, "comment": comment or ""}
            for mode, chunk in runner.resume(self.app, tid, answer):
                events.extend(self._translate(mode, chunk))
        st = self.status(tid)
        refused = st["paused_at_gate"] and bool(st["gate_error"])
        return {"ok": not refused, "error": st["gate_error"] if refused else None, "events": events, "summary": st}
