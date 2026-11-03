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
from typing import Any, Iterable, Optional

from obskit.analyze import percentile, span_cost
from obskit.exporters import by_trace, root_of

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


def request_rows(spans: Iterable[dict]) -> list[dict]:
    """One row per brain request: type, start, duration, error, cost (sum over the trace), LLM calls."""
    rows = []
    for tid, ss in by_trace(list(spans)).items():
        root = root_of(ss)
        a = root.get("attributes", {})
        kind = a.get("brain.request_type")
        if not kind:
            continue
        llm_calls = sum(1 for s in ss if s.get("attributes", {}).get("gen_ai.operation.name") in ("chat", "text_completion"))
        rows.append({"trace_id": tid, "type": kind, "t_ms": root["start_ms"], "duration_ms": root["duration_ms"],
                     "error": root.get("status") == "ERROR", "cost_usd": sum(span_cost(s) for s in ss),
                     "llm_calls": llm_calls, "intent": a.get("brain.intent"), "spans": len(ss)})
    return sorted(rows, key=lambda r: r["t_ms"])


def slo_report(spans: Iterable[dict]) -> dict:
    rows = request_rows(spans)
    out: dict = {"requests": len(rows), "by_type": {}}
    for kind in sorted({r["type"] for r in rows}):
        rs = [r for r in rows if r["type"] == kind]
        ok = [r for r in rs if not r["error"]]
        d = [r["duration_ms"] for r in ok]
        c = [r["cost_usd"] for r in rs]
        lat_t, cost_t = LATENCY_MS.get(kind, 8000.0), COST_USD.get(kind, 0.005)
        avail = len(ok) / len(rs) if rs else 1.0
        lat_good = sum(1 for x in d if x <= lat_t) / len(d) if d else 1.0
        out["by_type"][kind] = {
            "n": len(rs), "errors": len(rs) - len(ok), "availability": avail, "availability_ok": avail >= AVAILABILITY,
            "p50_ms": percentile(d, 50) if d else 0.0, "p95_ms": percentile(d, 95) if d else 0.0,
            "latency_target_ms": lat_t, "latency_sli": lat_good, "latency_ok": (percentile(d, 95) if d else 0) <= lat_t,
            "cost_mean_usd": sum(c) / len(c) if c else 0.0, "cost_p95_usd": percentile(c, 95) if c else 0.0,
            "cost_total_usd": sum(c), "cost_target_usd": cost_t,
            "cost_ok": (sum(c) / len(c) if c else 0.0) <= cost_t,
            "llm_calls_mean": sum(r["llm_calls"] for r in rs) / len(rs) if rs else 0.0,
        }
    return out


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
