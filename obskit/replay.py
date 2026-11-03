"""Replay a recorded LLM call: rebuild the exact request from a span and send it again.

This only works when the span carries content (gen_ai.input.messages and, if there was
one, gen_ai.system_instructions): with content capture off, a trace tells you THAT a
call was slow or failed, but not WHAT was asked. That is the real trade-off behind the
Opt-In: privacy versus the ability to reproduce.

    req = request_from_span(span)              # llmkit ChatRequest
    out = replay(span, llm)                     # {"original", "replayed", "same", ...}

Determinism: against mockllm or ragkit's ExtractiveAnswerer a replay is exact. Against a
real model, the same request can produce a different answer (sampling); compare meaning,
not bytes, or replay several times.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from opentelemetry import trace
from opentelemetry.trace import Link, SpanContext, TraceFlags

from . import semconv as sc
from .analyze import span_type
from .tracing import get_tracer, span as obs_span


def llm_spans(trace_spans) -> list[dict]:
    return sorted((s for s in trace_spans if span_type(s) == "llm"), key=lambda s: s["start_ms"])


def _texts(parts) -> str:
    return "".join(p.get("content", "") for p in parts if p.get("type") == "text")


def request_from_span(span: dict):
    """llmkit ChatRequest with the recorded system prompt, messages and max_tokens."""
    from llmkit import ChatRequest, Message
    a = span.get("attributes", {})
    if sc.INPUT_MESSAGES not in a:
        raise ValueError(f"span {span.get('span_id')} has no {sc.INPUT_MESSAGES}: it was recorded with "
                         "content capture off, so the request cannot be rebuilt")
    msgs = json.loads(a[sc.INPUT_MESSAGES])
    system = _texts(json.loads(a[sc.SYSTEM_INSTRUCTIONS])) if a.get(sc.SYSTEM_INSTRUCTIONS) else ""
    return ChatRequest(messages=[Message(m["role"], _texts(m.get("parts", []))) for m in msgs],
                       system=system, max_tokens=int(a.get(sc.REQUEST_MAX_TOKENS, 1024)))


def recorded_output(span: dict) -> Optional[str]:
    a = span.get("attributes", {})
    if sc.OUTPUT_MESSAGES not in a:
        return None
    msgs = json.loads(a[sc.OUTPUT_MESSAGES])
    return "".join(_texts(m.get("parts", [])) for m in msgs)


def replay(span: dict, llm: Any, *, tracer: Optional[trace.Tracer] = None) -> dict:
    """Send the recorded request to `llm` inside a 'replay' span that LINKS to the original
    span (a span link, not a parent: the replay is a new trace, related but separate)."""
    req = request_from_span(span)
    link = Link(SpanContext(int(span["trace_id"], 16), int(span["span_id"], 16), is_remote=True,
                            trace_flags=TraceFlags(TraceFlags.SAMPLED)))
    with obs_span("replay", type="agent", tracer=tracer or get_tracer(), links=[link],
                  attributes={sc.REPLAY_OF: span["trace_id"]}) as sp:
        res = llm.complete(req)
        replay_trace = format(sp.get_span_context().trace_id, "032x")
    original = recorded_output(span)
    return {"request": req, "original": original, "replayed": res.text, "result": res,
            "same": original is not None and original.strip() == res.text.strip(),
            "replay_trace_id": replay_trace}
