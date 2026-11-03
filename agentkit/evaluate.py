"""Evaluating agents by their trajectories (lesson 15, exercise 4 asks you to write
score_trajectory and summarize_scores in mine.py).

A final answer alone hides most of what matters in an agent: HOW it got there. These
functions read the trajectory records of a run (agentkit.trajectory) and compare them
with a gold outcome:

  success            the run ended normally (final_answer or gave_up), the outcome matches
                     the gold (a request with the right fields was filed, or none was),
                     required tools succeeded, forbidden tools did not, and the answer
                     contains the required facts
  steps, tool_calls  how long the path was (note calls are not counted as tool calls)
  redundant_calls    calls repeated with identical arguments after an earlier success
  efficiency         optimal_calls / tool_calls (capped at 1): 1.0 = the shortest path
  evidence_conflict  the answer names an approval route, but never the one check_policy returned
  cost_usd, tokens

A task file is JSONL, one task per line:
  {"id": "t01", "task": "...", "gold": {"outcome": "request_created" | "no_request" | "clarify",
    "request": {"employee": "E016", "system": "aws-production", "access_level": "admin",
                "duration_days": 3, "route": "needs_security"},
    "answer_contains": ["Michal Ben-David"], "answer_contains_any": [...],
    "required_tools": ["lookup_employee"], "forbidden_tools": ["create_access_request"],
    "optimal_calls": 3}}
"""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

ROUTES = ("auto_approve", "needs_manager", "needs_security")
SUCCESS_STOPS = ("final_answer", "gave_up")
LOCAL_TOOLS = ("note",)
REQUEST_FIELDS = {"employee": "employee_id", "system": "system", "access_level": "access_level",
                  "duration_days": "duration_days", "route": "route"}


def load_tasks(path: Union[str, Path]) -> list[dict]:
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def _calls(records: list[dict]) -> list[tuple[dict, dict]]:
    out = []
    for r in records:
        if r.get("type") == "step":
            out += list(zip(r.get("calls", []), r.get("results", [])))
    return out


def score_trajectory(records: list[dict], gold: dict, task_id: str = "") -> dict:
    """Score ONE run (the records of one run_id) against its gold outcome."""
    stop = next((r for r in reversed(records) if r.get("type") == "stop"), {})
    steps = [r for r in records if r.get("type") == "step"]
    pairs = [(c, res) for c, res in _calls(records) if c["name"] not in LOCAL_TOOLS]
    reasons: list[str] = []
    stop_reason = stop.get("reason", "missing_stop")
    text = stop.get("text", "") or ""
    low = text.lower()
    if stop_reason not in SUCCESS_STOPS:
        reasons.append(f"stopped: {stop_reason}")

    ok_tools = {c["name"] for c, res in pairs if not res.get("is_error")}
    for t in gold.get("required_tools", []):
        if t not in ok_tools:
            reasons.append(f"missing tool: {t}")
    for t in gold.get("forbidden_tools", []):
        if t in ok_tools:
            reasons.append(f"forbidden tool used: {t}")

    created = []
    for c, res in pairs:
        if c["name"] == "create_access_request" and not res.get("is_error"):
            try:
                created.append(json.loads(res.get("text", "{}")))
            except json.JSONDecodeError:
                created.append({})
    outcome = gold.get("outcome", "no_request")
    if outcome == "request_created":
        if len(created) != 1:
            reasons.append(f"expected 1 request, got {len(created)}")
        else:
            for key, value in (gold.get("request") or {}).items():
                got = created[0].get(REQUEST_FIELDS.get(key, key))
                if got != value:
                    reasons.append(f"request {key}: {got!r} != {value!r}")
    elif created:
        reasons.append(f"a request was created ({len(created)}) but none was expected")

    for s in gold.get("answer_contains", []):
        if s.lower() not in low:
            reasons.append(f"answer lacks {s!r}")
    anyof = gold.get("answer_contains_any") or []
    if anyof and not any(s.lower() in low for s in anyof):
        reasons.append(f"answer lacks any of {anyof}")

    policy_routes = set()
    for c, res in pairs:
        if c["name"] == "check_policy" and not res.get("is_error"):
            try:
                policy_routes.add(json.loads(res.get("text", "{}")).get("route"))
            except json.JSONDecodeError:
                pass
    mentioned = {r for r in ROUTES if r in low}
    conflict = bool(policy_routes and mentioned and not (mentioned & policy_routes))
    if conflict:
        reasons.append(f"answer names {sorted(mentioned)} but check_policy said {sorted(policy_routes)}")

    seen_ok: set[str] = set()
    redundant = 0
    for c, res in pairs:
        if c.get("fp") in seen_ok:
            redundant += 1
        if not res.get("is_error"):
            seen_ok.add(c.get("fp"))
    n_calls = len(pairs)
    optimal = gold.get("optimal_calls")
    if optimal is None:
        efficiency = None
    elif n_calls == 0:
        efficiency = 1.0 if optimal == 0 else 0.0
    else:
        efficiency = min(1.0, optimal / n_calls)
    return {
        "task_id": task_id or stop.get("task_id", ""),
        "success": not reasons,
        "reasons": reasons,
        "stop_reason": stop_reason,
        "steps": len(steps),
        "tool_calls": n_calls,
        "errors": sum(1 for _, res in pairs if res.get("is_error")),
        "redundant_calls": redundant,
        "efficiency": efficiency,
        "evidence_conflict": conflict,
        "requests_created": len(created),
        "cost_usd": float(stop.get("cost_usd", 0.0) or 0.0),
        "tokens": int(stop.get("input_tokens", 0) or 0) + int(stop.get("output_tokens", 0) or 0),
    }


def summarize_scores(scores: list[dict]) -> dict:
    n = len(scores)
    ok = [s for s in scores if s["success"]]
    calls = sum(s["tool_calls"] for s in scores)
    effs = [s["efficiency"] for s in scores if s.get("efficiency") is not None]
    cost = sum(s["cost_usd"] for s in scores)
    return {
        "tasks": n,
        "successes": len(ok),
        "success_rate": len(ok) / n if n else 0.0,
        "mean_steps": sum(s["steps"] for s in scores) / n if n else 0.0,
        "mean_tool_calls": calls / n if n else 0.0,
        "redundant_calls": sum(s["redundant_calls"] for s in scores),
        "redundancy_rate": sum(s["redundant_calls"] for s in scores) / calls if calls else 0.0,
        "errors": sum(s["errors"] for s in scores),
        "mean_efficiency": sum(effs) / len(effs) if effs else None,
        "evidence_conflicts": sum(1 for s in scores if s.get("evidence_conflict")),
        "cost_usd": cost,
        "cost_per_success": cost / len(ok) if ok else None,
        "stop_reasons": dict(Counter(s["stop_reason"] for s in scores)),
        "failed": [s["task_id"] for s in scores if not s["success"]],
    }


def format_summary(label: str, summ: dict, estimated: bool = False) -> str:
    cps = f"${summ['cost_per_success']:.5f}" if summ.get("cost_per_success") is not None else "n/a"
    eff = f"{summ['mean_efficiency']:.2f}" if summ.get("mean_efficiency") is not None else "n/a"
    est = "  (estimated tokens: fake model, priced like Haiku 5.5)" if estimated else ""
    return "\n".join([
        f"== {label}",
        f"  success {summ['successes']}/{summ['tasks']} ({summ['success_rate']:.0%})   mean steps {summ['mean_steps']:.2f}"
        f"   mean tool calls {summ['mean_tool_calls']:.2f}   efficiency {eff}",
        f"  redundant calls {summ['redundant_calls']} ({summ['redundancy_rate']:.0%})   tool errors {summ['errors']}"
        f"   evidence conflicts {summ['evidence_conflicts']}",
        f"  cost ${summ['cost_usd']:.5f}   per success {cps}{est}",
        "  stop reasons: " + ", ".join(f"{k}={v}" for k, v in sorted(summ["stop_reasons"].items())),
        "  failed: " + (", ".join(summ["failed"]) or "none"),
    ])


def run_tasks(make_agent: Callable[[Path], object], tasks: Iterable[dict], *,
              score: Callable[[list[dict], dict, str], dict] = score_trajectory,
              requests_dir: Optional[Path] = None) -> list[tuple[dict, object, dict]]:
    """Run every task with a FRESH agent and a fresh requests store (so idempotency keys
    from one task never deduplicate another), and score it.
    make_agent(requests_db_path) -> Agent. Returns [(task, AgentResult, score), ...]."""
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(requests_dir or tmp)
        for t in tasks:
            agent = make_agent(base / f"{t['id']}.db")
            res = agent.run(t["task"], task_id=t["id"])
            out.append((t, res, score(res.records, t["gold"], t["id"])))
    return out
