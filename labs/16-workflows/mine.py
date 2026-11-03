"""Your code for lesson 16. Each part is checked by tests in ./tests.

Reference versions live in flowkit/ (state.py, nodes.py). Try not to peek before your
tests pass. The graph itself is built by flowkit.graph.build_graph(deps, impl=...), which
swaps in whatever functions you implemented here.

    python -m pytest -q labs/16-workflows/tests/test_ex2_state.py   # part A
    python -m pytest -q labs/16-workflows/tests/test_ex3_nodes.py   # part B
    python -m pytest -q labs/16-workflows/tests/test_ex5_gate.py    # part C
    python -m pytest -q labs/16-workflows/tests                     # everything, incl. the contract tests

The state is a dict (a TypedDict, see flowkit/state.py) with these keys, filled as the
workflow advances:
    thread_id, requester, text, created_at          set by the caller at the start
    request       IntakeRequest.model_dump(): employee, system, access_level, external_sharing,
                  duration_days, justification
    employee      lookup_employee result: id, name, email, title, team, manager {id, name, email}
    requester_info, system_info, grants             more tool results
    policy        check_policy result: route, reasons, review_target, ...
    route         auto_approve | needs_manager | needs_security
    record        the filed request: id (AR-00001), status, route, approver, deduplicated
    risk_summary  text for the security reviewer
    decision      {gate, decision, actor_id, actor_name, comment}
    gate_error    {gate, message} or None
    status        received, extracted, enriched, routed, approved, pending_manager,
                  pending_security, rejected, expired, needs_info, already_granted, failed
    audit         list of events (reducer: merge_audit)
    usage         {calls, input_tokens, output_tokens, cost_usd} (reducer: add_usage)
Every node returns a PARTIAL update: only the keys it changes.
"""

from __future__ import annotations

from typing import Any, Optional

from langgraph.types import interrupt  # noqa: F401  (part C)

from flowkit.nodes import (INTAKE_SYSTEM, Deps, audit_event, call_tool, gate_payload,  # noqa: F401
                           idempotency_key, lookup_actor, progress, usage_of)
from flowkit.fake import SYSTEMS  # noqa: F401  (the known system names, for INTAKE_SYSTEM)
from flowkit.state import IntakeRequest  # noqa: F401
from flowkit import store  # noqa: F401
from llmkit.structured import StructuredError, complete_structured  # noqa: F401
from toolkit.registry import ToolError  # noqa: F401


# ================================================================== part A (exercise 2): reducers and routing
def merge_audit(left: Optional[list[dict]], right: Any) -> list[dict]:
    """Reducer for state["audit"]. LangGraph calls merge_audit(current_value, node_update).

    - left: the current list (may be None at the very start).
    - right: what a node returned for "audit": ONE event (a dict), a list of events, or None.
    - Return a NEW list: left's events in order, then right's events whose "id" is not
      already present (in left OR earlier in right). Do not mutate left.
    Why: a node may run twice for the same step (retry, resume after crash, a gate re-run),
    and event ids are deterministic, so duplicates must be dropped here.
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement merge_audit")


def add_usage(left: Optional[dict], right: Optional[dict]) -> dict:
    """Reducer for state["usage"]: sum {"calls", "input_tokens", "output_tokens", "cost_usd"}.

    - Either side may be None or miss keys: count them as 0.
    - Always return all four keys; cost_usd as a float. Return a NEW dict.
    Example: add_usage({"calls": 1, "cost_usd": 0.1}, {"calls": 2, "input_tokens": 5})
             -> {"calls": 3, "input_tokens": 5, "output_tokens": 0, "cost_usd": 0.1}
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement add_usage")


def route_after_file(state: dict) -> str:
    """Conditional edge after file_request. Return the NAME of the next node:
       status "pending_manager"  -> "manager_approval"
       status "pending_security" -> "risk_summary"   (the reviewer gets an LLM summary first)
       anything else (approved, failed, ...) -> "notify"
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement route_after_file")


def route_after_gate(state: dict) -> str:
    """Conditional edge after manager_approval and security_approval.
       state["gate_error"] is a dict {"gate": "manager"|"security", "message": ...}
           -> "<gate>_approval"  (the same gate runs again and pauses, showing the error)
       state["decision"] has decision "timeout" and gate "manager"
           -> "escalate"         (policy v2.2: no manager answer -> security reviews)
       otherwise (approve / reject, or a security timeout)
           -> "apply_decision"
    gate_error may be missing or None: both mean "no error".
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement route_after_gate")


# ================================================================== part B (exercise 3): nodes
def intake_node(state: dict, deps: Deps) -> dict:
    """LLM step: state["text"] (free text, untrusted) -> state["request"].

    1. prompt = f"Sender: {state['requester']}\\n<request>\\n{state['text']}\\n</request>"
    2. res = complete_structured(deps.llm, prompt, IntakeRequest, max_repairs=1, max_tokens=400,
                                 system=INTAKE_SYSTEM.format(systems=", ".join(SYSTEMS)))
    3. On StructuredError exc: return {"status": "needs_info", "error": <text that includes exc.stage>,
                                        "audit": [audit_event(state, deps, to="needs_info")]}
       (add "usage": usage_of(exc.result) when exc.result is not None)
    4. Otherwise req = res.value.model_dump(); if req["employee"] is empty, set it to
       state["requester"] (the sender asks for themselves).
       Return {"request": req, "status": "extracted", "usage": usage_of(res),
               "audit": [audit_event(state, deps, to="extracted")]}
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement intake_node")


def policy_node(state: dict, deps: Deps) -> dict:
    """Deterministic step: the route comes from check_policy, never from the LLM.

    pol = call_tool(deps, "check_policy", {
        "system": state["system_info"]["name"], "access_level": state["request"]["access_level"],
        "external_sharing": bool(state["request"].get("external_sharing")),
        "holds_customer_or_financial_data": None})
    Return {"policy": pol, "route": pol["route"], "status": "routed",
            "audit": [audit_event(state, deps, to="routed")]}
    Let ToolUnavailable propagate (the node's RetryPolicy retries it).
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement policy_node")


def file_request_node(state: dict, deps: Deps) -> dict:
    """Side effect: file the request ONCE, even if this node runs twice.

    1. rec = call_tool(deps, "create_access_request", {
           "employee": state["employee"]["id"], "system": state["system_info"]["name"],
           "access_level": state["request"]["access_level"],
           "justification": state["request"].get("justification") or "(none given)",
           "duration_days": state["request"].get("duration_days"),
           "idempotency_key": idempotency_key(state)})
       The same key returns the existing row with rec["deduplicated"] == True.
    2. status = rec["status"]  (approved | pending_manager | pending_security).
       The toolkit cannot see external_sharing, so its route may be LESS strict than
       state["route"]. If state["route"] == "needs_security" and rec["route"] != "needs_security":
           status = "pending_security"
           store.set_status(deps.requests_db, rec["id"], expected=rec["status"], to=status,
                            approver="security-team", route="needs_security")
           rec = {**rec, "status": status, "route": "needs_security"}
       (The reference also handles needs_manager over auto_approve; you don't have to.)
    3. ev = audit_event({**state, "record": rec}, deps, to=status, frm=None)
       store.write_audit(deps.requests_db, ev)      # durable audit row (idempotent by ev["id"])
    4. Return {"record": rec, "status": status, "audit": [ev]}
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement file_request_node")


# ================================================================== part C (exercise 5): the approval gate
def approval_gate(state: dict, deps: Deps, gate: str) -> dict:
    """Human in the loop. gate is "manager" or "security".

    1. answer = interrupt(gate_payload(state, gate))
       The first time, this PAUSES the graph (the payload goes to the caller). When someone
       resumes with Command(resume=value), LangGraph runs this node AGAIN from the top and
       interrupt() returns value. So nothing with a side effect may come before it.
    2. Validate the answer (a dict {"decision", "actor", "comment"}). If invalid, return
           {"gate_error": {"gate": gate, "message": <why>}}
       and the routing sends the graph back to this gate, which pauses again. Rules, in order:
       a. decision not in ("approve", "reject", "timeout")           -> invalid
       b. decision "timeout" (sent by the SLA timer): valid, no actor check. Return
          {"gate_error": None, "decision": {"gate": gate, "decision": "timeout",
           "actor_id": "system:sla-timer", "actor_name": "SLA timer", "comment": ...}}
       c. actor = lookup_actor(deps, answer["actor"]) is None          -> invalid ("unknown approver")
       d. actor["id"] is state["employee"]["id"] or state["requester_info"]["id"]
                                                                      -> invalid, message contains "own request"
       e. gate "security" and actor["team"] != deps.security_team    -> invalid, contains "only the security team"
       f. gate "manager" and actor is neither state["employee"]["manager"]["id"] nor in the
          security team                                               -> invalid, contains "manager"
       g. decision "reject" with an empty comment                    -> invalid, contains "comment"
    3. Valid: return {"gate_error": None, "decision": {"gate": gate, "decision": answer["decision"],
                      "actor_id": actor["id"], "actor_name": actor["name"], "comment": <stripped comment>}}
    (Authority comes from Acme's directory via lookup_actor, never from a role the caller claims.)
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement approval_gate")
