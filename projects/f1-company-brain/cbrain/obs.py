"""Observability for Company Brain: one trace per request, an SLO report, cost per request type.

The tracer provider is the one M1's Assistant already creates (obskit.setup_tracing with PII
redaction and a JSONL file): Company Brain opens its root span with the same tracer, so M1's spans
(route, retrieval, pack_context, the answer LLM call) become children of the brain's root.

Root spans (one per request, attribute brain.request_type):
    invoke_workflow company_brain.ask       intent route -> knowledge (M1's spans) or confirmation
    invoke_workflow company_brain.request   preview / start: flowkit's LLM and tool spans underneath
    invoke_workflow company_brain.decide    one approval decision: the resume of the paused graph

SLOs (targets for a 200-person internal tool; the numbers are a starting point, not a promise):
    availability   99.5% of requests do not fail (root span not ERROR)
    latency        ask p95 <= 8 s (an LLM answer), request p95 <= 5 s (intake + tools), decide p95 <= 3 s
    cost           ask <= $0.005, request <= $0.003, decide <= $0.001 per request
"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Any


LATENCY_MS = {"ask": 8000.0, "request": 5000.0, "decide": 3000.0}
COST_USD = {"ask": 0.005, "request": 0.003, "decide": 0.001}
AVAILABILITY = 0.995


def root_span(tracer: Any, kind: str, principal: Any = None, **attrs: Any):
    if tracer is None:
        return nullcontext(None)
    from obskit import agent_span
    a = {"brain.request_type": kind, **{f"brain.{k}": v for k, v in attrs.items() if v is not None}}
    if principal is not None:
        a["brain.user"] = principal.id
        a["brain.acl_role"] = principal.acl_role
    return agent_span(f"company_brain.{kind}", workflow=True, tracer=tracer, attributes=a)


@contextmanager
def child_span(tracer: Any, name: str, **attrs: Any):
    if tracer is None:
        yield None
        return
    from obskit import span
    with span(name, attributes={k: v for k, v in attrs.items() if v is not None}, tracer=tracer) as sp:
        yield sp


def request_rows(*args, **kwargs):
    """Milestone 9: runs your mine.request_rows (see cbrain/hooks.py)."""
    from .hooks import call
    return call("request_rows", *args, **kwargs)


def slo_report(*args, **kwargs):
    """Milestone 9: runs your mine.slo_report (see cbrain/hooks.py)."""
    from .hooks import call
    return call("slo_report", *args, **kwargs)


def format_slo(rep: dict) -> str:
    lines = [f"requests: {rep['requests']}"]
    for kind, m in rep["by_type"].items():
        mark = lambda ok: "ok " if ok else "BAD"  # noqa: E731
        lines.append(f"\n{kind}  (n={m['n']}, errors={m['errors']}, LLM calls/request={m['llm_calls_mean']:.2f})")
        lines.append(f"  [{mark(m['availability_ok'])}] availability {m['availability']:.3%}  (target {AVAILABILITY:.1%})")
        lines.append(f"  [{mark(m['latency_ok'])}] latency p50 {m['p50_ms']:.0f} ms, p95 {m['p95_ms']:.0f} ms "
                     f"(target p95 <= {m['latency_target_ms']:.0f} ms)")
        lines.append(f"  [{mark(m['cost_ok'])}] cost mean ${m['cost_mean_usd']:.5f}, p95 ${m['cost_p95_usd']:.5f}, "
                     f"total ${m['cost_total_usd']:.4f}  (target mean <= ${m['cost_target_usd']})")
    return "\n".join(lines)


def load_trace_file(path) -> list[dict]:
    from obskit.exporters import load_spans
    return load_spans(str(path))
