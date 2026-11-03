"""Running, resuming and inspecting workflow threads (lesson 16).

A "thread" is one access request: one thread_id, one line of checkpoints. These helpers
are what the lab's CLI scripts (run.py, approve.py, timetravel.py) are made of.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Iterator, Optional

from langgraph.types import Command

from .state import TERMINAL


def config(thread_id: str, checkpoint_id: Optional[str] = None) -> dict:
    c = {"configurable": {"thread_id": thread_id}}
    if checkpoint_id:
        c["configurable"]["checkpoint_id"] = checkpoint_id
    return c


def initial_state(thread_id: str, requester: str, text: str, created_at: str) -> dict:
    return {"thread_id": thread_id, "requester": requester, "text": text, "created_at": created_at,
            "status": "received", "audit": [], "usage": {}}


def stream(app, inp: Any, cfg: dict, *, durability: str = "sync") -> Iterator[tuple[str, Any]]:
    """Yield (mode, chunk) for stream_mode=["updates", "custom"]:
       ("updates", {node: partial_update})  after each node finishes
       ("updates", {"__interrupt__": (...)}) when a gate pauses
       ("custom", {"node", "msg", ...})      progress events the nodes send while working"""
    for mode, chunk in app.stream(inp, cfg, stream_mode=["updates", "custom"], durability=durability):
        yield mode, chunk


def start(app, thread_id: str, requester: str, text: str, created_at: str, **kw) -> Iterator[tuple[str, Any]]:
    return stream(app, initial_state(thread_id, requester, text, created_at), config(thread_id), **kw)


def resume(app, thread_id: str, value: Any = None, **kw) -> Iterator[tuple[str, Any]]:
    """value=None continues a thread that stopped (crash, kill, error); a value answers a
    pending interrupt (it becomes the return value of interrupt() inside the gate)."""
    inp = None if value is None else Command(resume=value)
    return stream(app, inp, config(thread_id), **kw)


def interrupts(snapshot) -> list:
    """Pending interrupts of a StateSnapshot (empty if the thread is not paused at a gate)."""
    return [i for t in snapshot.tasks for i in (t.interrupts or ())]


def summary(app, thread_id: str) -> dict:
    """Where a thread is: status, next nodes, pending gate payload, request id."""
    st = app.get_state(config(thread_id))
    v = st.values or {}
    ints = interrupts(st)
    return {"thread_id": thread_id, "status": v.get("status"), "next": list(st.next),
            "paused_at_gate": bool(ints), "gate": ints[0].value if ints else None,
            "request_id": (v.get("record") or {}).get("id"), "route": v.get("route"),
            "done": not st.next and v.get("status") in TERMINAL, "error": v.get("error")}


def thread_ids(saver) -> list[str]:
    """All thread ids in a checkpointer, oldest first."""
    seen: dict[str, str] = {}
    for t in saver.list(None):
        tid = t.config["configurable"]["thread_id"]
        ts = t.checkpoint.get("ts", "")
        seen[tid] = min(seen.get(tid, ts), ts)
    return sorted(seen, key=lambda k: seen[k])


def pending(app, saver) -> list[dict]:
    """Threads paused at an approval gate: the approver's inbox."""
    return [s for s in (summary(app, t) for t in thread_ids(saver)) if s["paused_at_gate"]]


def history(app, thread_id: str) -> list[dict]:
    """Checkpoints of a thread, OLDEST first (get_state_history returns newest first)."""
    rows = []
    for s in app.get_state_history(config(thread_id)):
        rows.append({"checkpoint_id": s.config["configurable"]["checkpoint_id"], "step": s.metadata.get("step"),
                     "source": s.metadata.get("source"), "next": list(s.next), "status": s.values.get("status"),
                     "parent": (s.parent_config or {}).get("configurable", {}).get("checkpoint_id"),
                     "created_at": s.created_at, "snapshot": s})
    return list(reversed(rows))


def fmt_event(mode: str, chunk: Any) -> str:
    """One line per streamed event, for the CLI."""
    if mode == "custom":
        return f"    . {chunk.get('node', '?'):<17} {chunk.get('msg', '')}"
    lines = []
    for node, upd in (chunk or {}).items():
        if node == "__interrupt__":
            for i in upd:
                v = i.value
                lines.append(f"  || PAUSED at {v.get('gate')}_approval ({v.get('request_id')}): waiting for "
                             f"{' or '.join(v.get('allowed_approvers', []))}"
                             + (f"  [previous answer refused: {v['previous_error']}]" if v.get("previous_error") else ""))
            continue
        upd = upd or {}
        keys = ", ".join(k for k in upd if k not in ("audit", "usage"))
        status = upd.get("status")
        lines.append(f"  > {node:<17} status={status or '-':<17} wrote: {keys}")
    return "\n".join(lines)


def print_events(events: Iterator[tuple[str, Any]], out: Callable[[str], None] = print) -> None:
    for mode, chunk in events:
        line = fmt_event(mode, chunk)
        if line:
            out(line)


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
