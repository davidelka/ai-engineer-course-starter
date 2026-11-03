"""Compare recorded runs: success rate, turns, cost and time per task and variant.

    python labs/05-coding-agents/report.py
    python labs/05-coding-agents/report.py --file results/runs.jsonl --task bugfix

Medians, not means: one run that loops for 60 turns should not decide the comparison.
With fewer than 3 runs per group the report says so, because a single run can point the
wrong way and still look convincing.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from collections import defaultdict

LAB = os.path.dirname(os.path.abspath(__file__))


def load(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def _med(values: list) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float))]
    return statistics.median(vals) if vals else None


def summarize(runs: list[dict]) -> dict[tuple[str, str], dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in runs:
        label = r.get("variant", "?")
        if r.get("variant") == "configured" and r.get("config"):
            label = f"configured({r['config']} config, {r.get('hooks')} hooks)"
        groups[(r["task"], label)].append(r)
    out = {}
    for key, rs in sorted(groups.items()):
        out[key] = {
            "runs": len(rs),
            "success": sum(1 for r in rs if r.get("success")),
            "acceptance": _med([r["acceptance_passed"] / r["acceptance_total"] for r in rs if r.get("acceptance_total")]),
            "turns": _med([r.get("num_turns") for r in rs]),
            "tool_calls": _med([r.get("tool_calls") for r in rs]),
            "cost": _med([r.get("total_cost_usd") for r in rs]),
            "seconds": _med([(r.get("duration_ms") or 0) / 1000 for r in rs if r.get("duration_ms")]),
            "blocked": sum(len(r.get("hook_blocked") or []) for r in rs),
            "injection": sum(1 for r in rs if r.get("injection_attempted")),
            "secret_reads": sum(r.get("secret_access_attempts") or 0 for r in rs),
            "leaks": sum(1 for r in rs if r.get("secret_leaked_to")),
        }
    return out


def fmt(v, kind=""):
    if v is None:
        return "-"
    if kind == "$":
        return f"${v:.3f}"
    if kind == "%":
        return f"{100 * v:.0f}%"
    return f"{v:.0f}" if isinstance(v, float) else str(v)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=os.path.join(LAB, "results", "runs.jsonl"))
    ap.add_argument("--task")
    a = ap.parse_args()
    runs = [r for r in load(a.file) if not a.task or r.get("task") == a.task]
    if not runs:
        print(f"No runs in {a.file}. Run run_agent.py first.")
        return
    for (task, label), s in summarize(runs).items():
        print(f"\n{task} / {label}  ({s['runs']} run{'s' if s['runs'] != 1 else ''})")
        print(f"  success           {s['success']}/{s['runs']}")
        print(f"  acceptance (med)  {fmt(s['acceptance'], '%')}")
        print(f"  turns (med)       {fmt(s['turns'])}     tool calls (med) {fmt(s['tool_calls'])}")
        print(f"  cost (med)        {fmt(s['cost'], '$')}   time (med) {fmt(s['seconds'])}s")
        print(f"  hook blocks       {s['blocked']}   injection attempts {s['injection']}   .env access attempts {s['secret_reads']}   leaks {s['leaks']}")
        if s["runs"] < 3:
            print("  note: fewer than 3 runs. Treat any difference as a hint, not a result.")


if __name__ == "__main__":
    main()
