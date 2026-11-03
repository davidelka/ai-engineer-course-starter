"""Aggregations over exported spans: latency percentiles per span type, cost per trace,
the slowest traces. Reference for lesson 22, exercise 3 (labs/22-observability/mine.py).

Everything takes span dicts (obskit.exporters format), so it runs on a JSONL file from
yesterday as easily as on spans in memory.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from . import semconv as sc
from .exporters import by_trace, root_of


def percentile(values: Sequence[float], p: float) -> float:
    """Linear interpolation between closest ranks (numpy's default, 'linear').

    rank = (n - 1) * p / 100; interpolate between values[floor(rank)] and values[ceil(rank)].
    percentile([1, 2, 3, 4], 50) == 2.5;  percentile([10], 95) == 10.
    Raises ValueError on an empty sequence (an empty p95 is a bug, not a zero)."""
    if not values:
        raise ValueError("percentile of an empty sequence")
    if not 0 <= p <= 100:
        raise ValueError("p must be between 0 and 100")
    xs = sorted(float(v) for v in values)
    rank = (len(xs) - 1) * p / 100.0
    lo, hi = math.floor(rank), math.ceil(rank)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (rank - lo)


def span_type(span: dict) -> str:
    """obskit.span.type if present, else derived from gen_ai.operation.name, else 'other'."""
    a = span.get("attributes", {})
    t = a.get(sc.SPAN_TYPE)
    if t:
        return str(t)
    return sc.TYPE_BY_OPERATION.get(a.get(sc.OPERATION, ""), "other")


def span_cost(span: dict) -> float:
    return float(span.get("attributes", {}).get(sc.COST_USD) or 0.0)


def is_error(span: dict) -> bool:
    return span.get("status") == "ERROR"


def summarize(spans: Iterable[dict], top_n: int = 5) -> dict:
    spans = list(spans)
    groups: dict[str, list[dict]] = {}
    for s in spans:
        groups.setdefault(span_type(s), []).append(s)
    by_type = {}
    for t, ss in sorted(groups.items()):
        d = [s["duration_ms"] for s in ss]
        by_type[t] = {"count": len(ss), "errors": sum(is_error(s) for s in ss),
                      "p50_ms": percentile(d, 50), "p95_ms": percentile(d, 95), "max_ms": max(d)}
    per_trace = {}
    for tid, ss in by_trace(spans).items():
        root = root_of(ss)
        per_trace[tid] = {"name": root["name"], "duration_ms": root["duration_ms"],
                          "cost_usd": sum(span_cost(s) for s in ss),
                          "llm_calls": sum(span_type(s) == "llm" for s in ss),
                          "error": any(is_error(s) for s in ss)}
    costs = [v["cost_usd"] for v in per_trace.values()]
    durs = [v["duration_ms"] for v in per_trace.values()]
    slowest = sorted(per_trace.items(), key=lambda kv: (-kv[1]["duration_ms"], kv[0]))[:top_n]
    return {
        "spans": len(spans),
        "traces": len(per_trace),
        "by_type": by_type,
        "per_trace": per_trace,
        "cost": {"total_usd": sum(costs),
                 "mean_per_trace_usd": (sum(costs) / len(costs)) if costs else 0.0,
                 "p95_per_trace_usd": percentile(costs, 95) if costs else 0.0},
        "latency": {"p50_ms": percentile(durs, 50) if durs else 0.0,
                    "p95_ms": percentile(durs, 95) if durs else 0.0},
        "slowest": [{"trace_id": tid, "name": v["name"], "duration_ms": v["duration_ms"]} for tid, v in slowest],
    }


def ttft_stats(spans: Iterable[dict]) -> dict:
    """p50/p95 time to first chunk (seconds) over LLM spans that streamed."""
    xs = [float(s["attributes"][sc.TIME_TO_FIRST_CHUNK]) for s in spans
          if sc.TIME_TO_FIRST_CHUNK in s.get("attributes", {})]
    if not xs:
        return {"count": 0}
    return {"count": len(xs), "p50_s": percentile(xs, 50), "p95_s": percentile(xs, 95)}


def tokens(spans: Iterable[dict]) -> dict:
    """Token totals over LLM spans, with the prompt-cache read share."""
    inp = out = cread = cwrite = 0
    for s in spans:
        a = s.get("attributes", {})
        inp += int(a.get(sc.USAGE_INPUT, 0) or 0)
        out += int(a.get(sc.USAGE_OUTPUT, 0) or 0)
        cread += int(a.get(sc.USAGE_CACHE_READ, 0) or 0)
        cwrite += int(a.get(sc.USAGE_CACHE_WRITE, 0) or 0)
    return {"input": inp, "output": out, "cache_read": cread, "cache_write": cwrite,
            "cache_read_share": (cread / inp) if inp else 0.0}


def format_summary(summary: dict, *, top_n: int = 5) -> str:
    """Plain-text report used by trace_stats.py."""
    lines = [f"{summary['traces']} traces, {summary['spans']} spans", "", "latency by span type (ms):"]
    for t, v in summary["by_type"].items():
        lines.append(f"  {t:<10} n={v['count']:<5} p50={v['p50_ms']:>9.1f}  p95={v['p95_ms']:>9.1f}  "
                     f"max={v['max_ms']:>9.1f}  errors={v['errors']}")
    c = summary["cost"]
    lines += ["", f"cost: total ${c['total_usd']:.6f}   mean/trace ${c['mean_per_trace_usd']:.6f}   "
                  f"p95/trace ${c['p95_per_trace_usd']:.6f}",
              f"request latency: p50 {summary['latency']['p50_ms']:.0f} ms   p95 {summary['latency']['p95_ms']:.0f} ms",
              "", f"slowest {min(top_n, len(summary['slowest']))} traces:"]
    for r in summary["slowest"][:top_n]:
        pt = summary["per_trace"].get(r["trace_id"], {})
        flag = "  ERROR" if pt.get("error") else ""
        lines.append(f"  {r['trace_id'][:12]}  {r['duration_ms']:>9.1f} ms  ${pt.get('cost_usd', 0):.6f}  "
                     f"llm_calls={pt.get('llm_calls', 0)}  {r['name']}{flag}")
    return "\n".join(lines)
