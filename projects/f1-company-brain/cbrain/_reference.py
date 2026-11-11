"""Reference implementations of the F1 milestones (solutions branch only).

This file exists only on the `solutions` branch of the course repo. On `main` Company Brain runs
your functions from mine.py, and a milestone you have not written yet stops the command with a
message that names it. Compare with this file AFTER your tests pass.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace
from typing import Any, Callable, Iterable, Optional

from guardkit.answerer import CANARY
from guardkit.models import DATAMARK
from guardkit.validate import check_output
from obskit.analyze import percentile, span_cost
from obskit.exporters import by_trace, root_of

from cbrain.guards import _SOURCE_RE, LEVELS
from cbrain.obs import AVAILABILITY, COST_USD, LATENCY_MS
from cbrain.router import (ACCESS_OBJECT_RE, ACCESS_WORD_RE, DATA_RE, INTENTS, POLICY_QUESTION_RE, QUESTION_RE, REQUEST_RE,
                     ROUTER_SYSTEM, IntentDecision, RouteResult)


def _wilson(k: int, n: int) -> tuple[float, float]:
    from evalkit.stats import wilson_ci
    ci = wilson_ci(k, n)
    return (round(ci.low, 3), round(ci.high, 3))


def rule_intent(text: str) -> dict:
    """Reference for milestone 3 (mine.rule_intent has the full specification)."""
    t = (text or "").strip()
    if not t:
        return {"intent": None, "confidence": 0.0, "matched": []}
    request = bool(REQUEST_RE.search(t) and ACCESS_OBJECT_RE.search(t))
    policy_q = bool(POLICY_QUESTION_RE.search(t))
    matched = (["request"] if request else []) + (["policy_question"] if policy_q else [])
    if request and not policy_q:
        return {"intent": "access_request", "confidence": 0.9, "matched": matched}
    if request and policy_q:
        return {"intent": None, "confidence": 0.5, "matched": matched}
    if policy_q:
        return {"intent": "knowledge", "confidence": 0.85, "matched": matched}
    from acmeqa.router import route_question
    r = route_question(t)
    if r.kind == "data":
        return {"intent": "data", "confidence": 0.8, "matched": [f"data:{m}" for m in r.matched]}
    if DATA_RE.search(t):
        return {"intent": "data", "confidence": 0.8, "matched": ["data_rule"]}
    if ACCESS_WORD_RE.search(t) and not QUESTION_RE.search(t):
        return {"intent": None, "confidence": 0.4, "matched": ["access_word"]}
    return {"intent": "knowledge", "confidence": 0.6, "matched": ["default"]}


def route_message(text: str, *, rules: Callable, llm: Any = None, llm_mode: str = "auto",
                  min_confidence: float = 0.5) -> RouteResult:
    rv = rules(text)
    if rv.get("intent") and llm_mode != "always":
        return RouteResult(rv["intent"], float(rv["confidence"]), "rules", list(rv.get("matched", [])))
    if llm is None or llm_mode == "never":
        return RouteResult(rv.get("intent") or "knowledge", float(rv.get("confidence") or 0.0), "fallback",
                           list(rv.get("matched", [])), reason="rules unsure, no model: safe default")
    from llmkit.errors import LLMError
    from llmkit.structured import StructuredError, complete_structured
    prompt = f"<message>\n{text}\n</message>"
    try:
        res = complete_structured(llm, prompt, IntentDecision, system=ROUTER_SYSTEM, max_repairs=1,
                                  max_tokens=200)
    except (StructuredError, LLMError) as exc:
        return RouteResult("knowledge", 0.0, "fallback", list(rv.get("matched", [])),
                           reason=f"router model failed ({type(exc).__name__}): safe default")
    d: IntentDecision = res.value
    info = {"intent": d.intent, "confidence": d.confidence, "cost_usd": res.cost_usd or 0.0,
            "input_tokens": res.input_tokens, "output_tokens": res.output_tokens}
    if d.confidence < min_confidence:
        return RouteResult("knowledge", d.confidence, "fallback", list(rv.get("matched", [])),
                           reason=f"model unsure ({d.intent}, {d.confidence:.2f}): safe default", llm=info)
    return RouteResult(d.intent, d.confidence, "llm", list(rv.get("matched", [])), reason=d.reason, llm=info)



def approvals_for(principal, items: list[dict]) -> list[dict]:
    """Reference for mine.approvals_for (see its docstring)."""
    me = getattr(principal, "employee_id", None)
    if not me:
        return []
    out = []
    for it in items:
        if me in (it.get("employee_id"), it.get("requester_id")):
            continue
        if getattr(principal, "is_security", False) or (it.get("gate") == "manager" and it.get("manager_id") == me):
            out.append(it)
    return sorted(out, key=lambda it: it.get("created_at") or "")


def harden_route(policy: dict, flags: list[str]) -> dict:
    """Reference for mine.harden_route (see its docstring)."""
    out = dict(policy)
    reasons = list(policy.get("reasons") or [])
    route = policy.get("route")
    if route not in ("auto_approve", "needs_manager", "needs_security"):
        out.update(route="needs_security", reasons=reasons + [f"unknown route {route!r}: failing closed"],
                   hardened=True)
        return out
    if not flags:
        out["hardened"] = False
        out["reasons"] = reasons
        return out
    note = f"suspicious request text ({', '.join(flags)}): never auto-approved"
    out.update(route="needs_manager" if route == "auto_approve" else route, reasons=reasons + [note], hardened=True)
    return out


def screen_hits(hits: list, screen: Callable) -> tuple[list, list[dict]]:
    kept, dropped = [], []
    for h in hits:
        r = screen(h.chunk.text)
        if r.flagged:
            dropped.append({"doc_id": h.chunk.doc_id, "chunk_id": h.chunk.id, "reasons": r.reasons})
        else:
            kept.append(h)
    return [replace(h, rank=i + 1) for i, h in enumerate(kept)], dropped



def spotlight_sources(user: str, nonce: str) -> str:
    """Wrap the body of every acmeqa <source ...> block in nonce markers and datamark it."""
    def one(m: re.Match) -> str:
        sid = re.search(r'\bid="?(\d+)', m.group(1))
        body = re.sub(r"[ \t]+", DATAMARK, m.group(2))
        tag = sid.group(1) if sid else "?"
        return (f"{m.group(1)}<<untrusted id={tag} nonce={nonce}>>\n{body}\n<</untrusted nonce={nonce}>>"
                f"{m.group(3)}")
    return _SOURCE_RE.sub(one, user)


def validate_output(text: str) -> list[dict]:
    """guardkit's output validator + the canary. [] = clean."""
    out = [{"kind": f.kind, "detail": f.detail} for f in check_output(text or "")]
    if CANARY in (text or ""):
        out.append({"kind": "secret_leak", "detail": "system prompt canary"})
    return out


def request_classification(chunks_meta: list[dict], floor: Optional[str] = "internal") -> str:
    """Reference for mine.request_classification (see its docstring)."""
    def level(v: Any) -> int:
        s = str(v or "").strip().lower()
        if not s:
            return LEVELS.index("internal")
        return LEVELS.index(s) if s in LEVELS else LEVELS.index("restricted")
    best = level(floor or "internal")
    for m in chunks_meta or []:
        best = max(best, level((m or {}).get("classification")))
    return LEVELS[best]


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


def route_metrics(rows: list[dict]) -> dict:
    n = len(rows)
    ok = sum(r["pred"] == r["label"] for r in rows)
    per = {}
    for c in INTENTS:
        tp = sum(1 for r in rows if r["pred"] == c and r["label"] == c)
        pp = sum(1 for r in rows if r["pred"] == c)
        ap = sum(1 for r in rows if r["label"] == c)
        per[c] = {"precision": tp / pp if pp else None, "recall": tp / ap if ap else None, "n": ap}
    conf = Counter(f"{r['label']}->{r['pred']}" for r in rows if r["pred"] != r["label"])
    return {"n": n, "accuracy": ok / n if n else 0.0, "ci95": _wilson(ok, n), "per_class": per,
            "llm_calls": sum(1 for r in rows if r["source"] == "llm" or r.get("llm_called")),
            "llm_rate": sum(1 for r in rows if r.get("llm_called")) / n if n else 0.0,
            "errors_by_direction": dict(conf), "cost_usd": round(sum(r["cost"] for r in rows), 6),
            "errors": [{"id": r["id"], "label": r["label"], "pred": r["pred"], "source": r["source"]}
                       for r in rows if r["pred"] != r["label"]]}
