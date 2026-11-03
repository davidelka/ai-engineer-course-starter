"""The workflow's typed state, its reducers, and the intake schema (lesson 16).

LangGraph keeps ONE state object per thread. Every node receives the current state and
returns a PARTIAL update (a dict with only the keys it changed). For each key, a reducer
decides how the update is merged:
  - no reducer (the default)  -> the new value replaces the old one
  - Annotated[list, merge_audit] -> merge_audit(old, new) decides

Everything in the state must be serializable, because a checkpointer writes it to disk
after every step. That is why the state holds plain dicts (request.model_dump()), not
Pydantic objects or open connections: the next process that resumes this thread must be
able to read it back without your Python objects.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------- statuses
# The request's lifecycle. The first three come from the requests store (toolkit), the rest
# are decided by the workflow. TERMINAL statuses end the thread.
Status = Literal["received", "extracted", "enriched", "routed",
                 "approved", "pending_manager", "pending_security",
                 "rejected", "expired", "needs_info", "already_granted", "failed"]
TERMINAL = {"approved", "rejected", "expired", "needs_info", "already_granted", "failed"}

Level = Literal["read", "viewer", "member", "editor", "write", "admin", "owner"]


# ---------------------------------------------------------------- intake schema (lesson 3's idea, toolkit's levels)
class IntakeRequest(BaseModel):
    """What the intake LLM step must extract from the employee's free text.

    Lesson 3 extracted a richer AccessRequest that also guessed the route. Here the route is
    NOT extracted: it is computed by check_policy (deterministic code). The LLM only turns
    language into fields; the levels match the toolkit's check_policy input exactly.
    """

    model_config = ConfigDict(extra="forbid")

    employee: Optional[str] = Field(
        None, description="Who needs the access: a work email or full name exactly as written. "
                          "null if the sender asks for themselves.")
    system: str = Field(description="The Acme system, lowercase with dashes, from the list of known systems "
                                    "(e.g. 'figma', 'aws-production', 'google-workspace').")
    access_level: Level = Field(description="read / viewer / member = basic seat; editor = paid seat; "
                                            "write = write access; admin / owner = admin rights.")
    external_sharing: bool = Field(description="true if company data goes to an external party or a "
                                               "third-party OAuth app is connected to Google Workspace.")
    duration_days: Optional[int] = Field(None, ge=1, le=365, description="Requested duration in days, only if stated.")
    justification: Optional[str] = Field(None, description="Why the access is needed, in a few words.")

    @field_validator("system")
    @classmethod
    def _normalize_system(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "-").replace("_", "-")


# ---------------------------------------------------------------- reducers (reference for exercise 2)
def merge_audit(left: Optional[list[dict]], right: Any) -> list[dict]:
    """Append audit events, ignoring events whose "id" is already present.

    Why dedupe: a node can run more than once for the same logical step (retry after a
    timeout, resume after a crash, an approval gate re-run on resume). Event ids are
    deterministic (thread + transition), so the second copy of an event is dropped.
    `right` may be one event (dict), a list of events, or None. Never mutates `left`.
    """
    out = list(left or [])
    if right is None:
        return out
    seen = {e.get("id") for e in out}
    for ev in ([right] if isinstance(right, dict) else list(right)):
        if ev.get("id") in seen:
            continue
        seen.add(ev.get("id"))
        out.append(ev)
    return out


USAGE_KEYS = ("calls", "input_tokens", "output_tokens", "cost_usd")


def add_usage(left: Optional[dict], right: Optional[dict]) -> dict:
    """Sum LLM usage across nodes: {"calls", "input_tokens", "output_tokens", "cost_usd"}.
    Missing keys count as 0, None counts as empty. Returns a new dict."""
    out = {k: 0 for k in USAGE_KEYS}
    out["cost_usd"] = 0.0
    for part in (left or {}, right or {}):
        for k in USAGE_KEYS:
            out[k] += part.get(k, 0) or 0
    out["cost_usd"] = round(out["cost_usd"], 8)
    return out


# ---------------------------------------------------------------- the state type
def make_state(merge_audit=merge_audit, add_usage=add_usage) -> type:
    """Build the state TypedDict with the given reducers (the lab passes its own from mine.py).

    total=False: every key is optional, because the state grows as the workflow advances.
    """
    return TypedDict("FlowState", {
        "thread_id": str,            # = the LangGraph thread id; also the base of idempotency keys
        "requester": str,            # the authenticated sender (like X-Actor in SPEC-006), never from the text
        "text": str,                 # the free-text request (untrusted)
        "created_at": str,
        "request": dict,             # IntakeRequest.model_dump()
        "employee": dict,            # lookup_employee result for who needs the access
        "requester_info": dict,      # lookup_employee result for the sender
        "system_info": dict,         # get_system_info result
        "grants": list,              # current grants on that system
        "policy": dict,              # check_policy result (route, reasons, review_target)
        "route": str,                # auto_approve | needs_manager | needs_security
        "record": dict,              # the filed request (create_access_request result)
        "risk_summary": str,         # LLM-written summary for the security reviewer
        "decision": dict,            # the last valid human decision
        "gate_error": Optional[dict],  # why the last decision was refused, shown at the next pause
        "status": str,
        "error": Optional[str],
        "notifications": list,
        "audit": Annotated[list, merge_audit],
        "usage": Annotated[dict, add_usage],
    }, total=False)


FlowState = make_state()
