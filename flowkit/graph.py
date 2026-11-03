"""Building and compiling the access-request workflow with LangGraph (lesson 16).

    from flowkit import Deps, FakeLLM, build_graph, open_checkpointer
    deps = Deps(llm=FakeLLM(), registry=acme_registry(requests_db=db), requests_db=db)
    app = build_graph(deps, checkpointer=open_checkpointer("results/checkpoints.db"))
    cfg = {"configurable": {"thread_id": "req-001"}}
    app.invoke({"thread_id": "req-001", "requester": "dana.levi@acme.example",
                "text": "I need a Figma editor seat"}, cfg)          # pauses at manager_approval
    app.invoke(Command(resume={"decision": "approve", "actor": "E005", "comment": "ok"}), cfg)

The graph (conditional edges in brackets):

    START -> intake -[needs_info]-> notify
                    -> enrich -[needs_info | already_granted]-> notify
                              -> policy -> file_request -[approved]-> notify
                                                        -[pending_manager]-> manager_approval
                                                        -[pending_security]-> risk_summary -> security_approval
    manager_approval  -[refused]-> manager_approval  -[timeout]-> escalate -> risk_summary
                      -[approve | reject]-> apply_decision
    security_approval -[refused]-> security_approval -[approve | reject | timeout]-> apply_decision
    apply_decision -> notify -> END
"""

from __future__ import annotations

import functools
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from . import nodes as ref
from .state import add_usage as ref_add_usage
from .state import make_state
from .state import merge_audit as ref_merge_audit

# Retry only what is worth retrying: a tool that timed out. LangGraph's default retry_on
# does NOT retry OSError, and TimeoutError is an OSError subclass, so a custom exception
# (ToolUnavailable) plus an explicit retry_on is clearer than relying on the default.
DEFAULT_RETRY = RetryPolicy(max_attempts=3, initial_interval=0.5, backoff_factor=2.0, max_interval=5.0,
                            jitter=True, retry_on=ref.ToolUnavailable)

# Names that impl (e.g. the lab's mine.py) may override.
OVERRIDABLE = ("merge_audit", "add_usage", "route_after_file", "route_after_gate", "intake_node", "policy_node",
               "file_request_node", "approval_gate")


def _impl(impl: Any) -> SimpleNamespace:
    base = {"merge_audit": ref_merge_audit, "add_usage": ref_add_usage, "route_after_file": ref.route_after_file,
            "route_after_gate": ref.route_after_gate, "intake_node": ref.intake_node, "policy_node": ref.policy_node,
            "file_request_node": ref.file_request_node, "approval_gate": ref.approval_gate}
    if impl is not None:
        for name in OVERRIDABLE:
            fn = getattr(impl, name, None)
            if callable(fn):
                base[name] = fn
    return SimpleNamespace(**base)


def build_graph(deps: "ref.Deps", *, impl: Any = None, checkpointer: Any = None,
                retry: Optional[RetryPolicy] = DEFAULT_RETRY, compile: bool = True):
    """The StateGraph of the workflow, compiled with `checkpointer` (None = no persistence,
    which also means no interrupts: a gate needs a checkpointer to pause)."""
    f = _impl(impl)
    State = make_state(f.merge_audit, f.add_usage)
    g = StateGraph(State)
    bind = lambda fn, **kw: functools.partial(fn, deps=deps, **kw)  # noqa: E731
    failure = bind(ref.on_node_failure)
    tools_kw = {"retry_policy": retry, "error_handler": failure} if retry else {"error_handler": failure}

    g.add_node("intake", bind(f.intake_node))  # llmkit already retries transport errors: no second layer here
    g.add_node("enrich", bind(ref.enrich_node), **tools_kw)
    g.add_node("policy", bind(f.policy_node), **tools_kw)
    g.add_node("file_request", bind(f.file_request_node), **tools_kw)  # safe to retry: idempotency key
    g.add_node("escalate", bind(ref.escalate_node))
    g.add_node("risk_summary", bind(ref.risk_summary_node))
    g.add_node("manager_approval", bind(f.approval_gate, gate="manager"))
    g.add_node("security_approval", bind(f.approval_gate, gate="security"))
    g.add_node("apply_decision", bind(ref.apply_decision_node))
    g.add_node("notify", bind(ref.notify_node))

    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", ref.route_after_intake, ["enrich", "notify"])
    g.add_conditional_edges("enrich", ref.route_after_enrich, ["policy", "notify"])
    g.add_edge("policy", "file_request")
    g.add_conditional_edges("file_request", f.route_after_file, ["notify", "manager_approval", "risk_summary"])
    g.add_conditional_edges("manager_approval", f.route_after_gate,
                            ["manager_approval", "escalate", "apply_decision"])
    g.add_edge("escalate", "risk_summary")
    g.add_edge("risk_summary", "security_approval")
    g.add_conditional_edges("security_approval", f.route_after_gate, ["security_approval", "apply_decision"])
    g.add_edge("apply_decision", "notify")
    g.add_edge("notify", END)
    return g.compile(checkpointer=checkpointer) if compile else g


def open_checkpointer(path: Path | str) -> SqliteSaver:
    """A SqliteSaver on a file. check_same_thread=False because LangGraph runs nodes in a
    thread pool. The tables are created on first use."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))
