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

Each docstring is a contract: what goes in, what comes out, and the rules the result must follow.
When you are stuck, HINTS.md has graded hints for every function (direction, structure, full algorithm).
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
    - Returns a NEW list: left's events in order, then the new events from right, in order.
      An event whose "id" is already present (in left or earlier in right) is dropped: the
      first copy wins. left is never mutated.
    Why: a node may run twice for the same step (retry, resume after crash, a gate re-run),
    and event ids are deterministic, so duplicates must be dropped here.

    Stuck? HINTS.md -> merge_audit
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement merge_audit")


def add_usage(left: Optional[dict], right: Optional[dict]) -> dict:
    """Reducer for state["usage"]: sum {"calls", "input_tokens", "output_tokens", "cost_usd"}.

    - Either side may be None or miss keys: count them as 0.
    - Always return all four keys; cost_usd as a float. Return a NEW dict (inputs unchanged).
    Example: add_usage({"calls": 1, "cost_usd": 0.1}, {"calls": 2, "input_tokens": 5})
             -> {"calls": 3, "input_tokens": 5, "output_tokens": 0, "cost_usd": 0.1}

    Stuck? HINTS.md -> add_usage
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement add_usage")


def route_after_file(state: dict) -> str:
    """Conditional edge after file_request. Return the NAME of the next node:
       status "pending_manager"  -> "manager_approval"
       status "pending_security" -> "risk_summary"   (the reviewer gets an LLM summary first)
       anything else (approved, failed, ...) -> "notify"

    Stuck? HINTS.md -> route_after_file
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement route_after_file")


def route_after_gate(state: dict) -> str:
    """Conditional edge after manager_approval and security_approval. Return the next node's name.
       a gate error (state["gate_error"] = {"gate": "manager"|"security", "message": ...})
           -> "<gate>_approval"  (the same gate runs again and pauses, showing the error)
       a manager timeout (decision "timeout" at gate "manager")
           -> "escalate"         (policy v2.2: no manager answer -> security reviews)
       anything else (approve / reject, or a security timeout)
           -> "apply_decision"
    gate_error may be missing or None: both mean "no error".

    Stuck? HINTS.md -> route_after_gate
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement route_after_gate")


# ================================================================== part B (exercise 3): nodes
def intake_node(state: dict, deps: Deps) -> dict:
    """LLM step: state["text"] (free text, untrusted) -> state["request"] (IntakeRequest fields).

    - One complete_structured call into IntakeRequest (native structured output), with
      system=INTAKE_SYSTEM filled with the known SYSTEMS, max_tokens=400 and ONE repair attempt.
      The prompt names the sender (state["requester"]) and wraps the untrusted text in
      <request>...</request>.
    - An empty employee means the sender asks for themselves: use state["requester"].
    - Success returns {"request", "status": "extracted", "usage", "audit": [one event]}.
    - A StructuredError is not raised: return {"status": "needs_info", "error": <text that
      includes exc.stage>, "audit": [one event]}, plus "usage" when the failed call has a result.
    Usage comes from usage_of(...); audit events from audit_event(state, deps, to=<new status>).

    Stuck? HINTS.md -> intake_node
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement intake_node")


def policy_node(state: dict, deps: Deps) -> dict:
    """Deterministic step: the route comes from the check_policy tool, never from the LLM.

    Call check_policy (via call_tool) with the system's name from state["system_info"], the
    request's access_level, its external_sharing as a bool, and
    holds_customer_or_financial_data=None (let the tool decide from its own data).
    Return {"policy": <the tool result>, "route": <its route>, "status": "routed",
            "audit": [audit_event(state, deps, to="routed")]}.
    Let ToolUnavailable propagate (the node's RetryPolicy retries it).

    Stuck? HINTS.md -> policy_node
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement policy_node")


def file_request_node(state: dict, deps: Deps) -> dict:
    """Side effect: file the request ONCE, even if this node runs twice.

    - Files it with the create_access_request tool (employee id, system name, access_level,
      justification or "(none given)", duration_days), passing idempotency_key(state): the same
      key returns the existing row with rec["deduplicated"] == True instead of a second row.
    - status = the record's status (approved | pending_manager | pending_security). The toolkit
      cannot see external_sharing, so its route may be LESS strict than state["route"]. When
      state["route"] is "needs_security" and the record's is not, raise it: status
      "pending_security", route "needs_security", approver "security-team", both in the
      returned record AND in the database row (flowkit.store).
      (The reference also handles needs_manager over auto_approve; you don't have to.)
    - Writes one durable audit row for the transition (to=status, from None) with
      store.write_audit; it is idempotent by event id.
    - Returns {"record": rec, "status": status, "audit": [that event]}.

    Stuck? HINTS.md -> file_request_node
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement file_request_node")


# ================================================================== part C (exercise 5): the approval gate
def approval_gate(state: dict, deps: Deps, gate: str) -> dict:
    """Human in the loop. gate is "manager" or "security".

    Pauses with interrupt(gate_payload(state, gate)). On resume LangGraph runs this node AGAIN
    from the top and interrupt() returns the answer, so nothing with a side effect may come
    before it. The answer is a dict {"decision", "actor", "comment"}.

    Invalid answer -> {"gate_error": {"gate": gate, "message": <why>}} (the routing sends the graph
    back to this gate, which pauses again). The message must contain the quoted word:
      - decision not "approve", "reject" or "timeout"                        -> "decision"
      - an actor not found by lookup_actor(deps, answer["actor"])            -> "unknown"
      - the actor is the employee or the requester                           -> "own request"
      - security gate, actor["team"] is not deps.security_team               -> "only the security team"
      - manager gate, actor neither the employee's manager nor on that team  -> "manager"
      - "reject" with an empty comment                                       -> "comment"
    A "timeout" (sent by the SLA timer) skips the actor checks; its actor is
    "system:sla-timer" / "SLA timer".
    Valid -> {"gate_error": None, "decision": {"gate", "decision", "actor_id", "actor_name",
              "comment" (stripped)}}.
    (Authority comes from Acme's directory via lookup_actor, never from a role the caller claims.)

    Stuck? HINTS.md -> approval_gate
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement approval_gate")
