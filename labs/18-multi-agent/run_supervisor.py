"""Exercise 3: the supervisor. Delegation as tool calls, context isolation, parallel workers.

    python labs/18-multi-agent/run_supervisor.py x01
    python labs/18-multi-agent/run_supervisor.py x08 --sequential
    python labs/18-multi-agent/run_supervisor.py x08 --show            # every agent's trajectory
    python labs/18-multi-agent/run_supervisor.py x01 --model anthropic:claude-haiku-5-5 --approve ask
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import _lab  # noqa: F401
from _lab import money, task_text
from agentkit import format_trajectory
from multikit import attribute_failure, build, format_attribution, aggregate_runs, score_multi


def first_prompt(run) -> int:
    step = next((r for r in run.records if r.get("type") == "step"), {})
    return int(step.get("tokens_in", 0) or 0)


def max_prompt(run) -> int:
    return max([int(r.get("tokens_in", 0) or 0) for r in run.records if r.get("type") == "step"] or [0])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task", nargs="?", default="x01")
    ap.add_argument("--model", default="fake")
    ap.add_argument("--sequential", action="store_true", help="fake supervisor delegates one worker per turn")
    ap.add_argument("--approve", default="yes", choices=["yes", "no", "ask"])
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    tid, text, gold = task_text(a.task)

    def confirm(call):
        if a.approve == "ask":
            return input(f"\n>>> run {call.name}({json.dumps(call.arguments)})? [y/N] ").strip().lower() in ("y", "yes")
        return a.approve == "yes"

    with tempfile.TemporaryDirectory() as tmp:
        sup = build("supervisor", a.model, requests_db=Path(tmp) / "s.db", confirm=confirm, parallel=not a.sequential)
        res = sup.run(text, task_id=tid)
        single = build("single", a.model, requests_db=Path(tmp) / "x.db", confirm=confirm).run(text, task_id=tid)
    print(f"TASK {tid}: {text}\n")
    root = res.runs[0]
    for r in root.records:
        if r.get("type") == "step":
            for c in r.get("calls", []):
                print(f"  supervisor step {r['n']}: {c['name']}(task={c['arguments'].get('task')!r})")
    print("\nCONTEXT PER AGENT (input tokens of the first step / the largest step):")
    for run in res.runs:
        print(f"  {run.agent:<11} {run.role:<11} first={first_prompt(run):>6,}  largest={max_prompt(run):>6,}  "
              f"total tokens={run.tokens:>7,}  {money(run.cost_usd)}")
    s0 = single.runs[0]
    print(f"  {'single':<11} {'(baseline)':<11} first={first_prompt(s0):>6,}  largest={max_prompt(s0):>6,}  "
          f"total tokens={s0.tokens:>7,}  {money(s0.cost_usd)}")
    agg = aggregate_runs(res.records)
    print("\nATTRIBUTION (supervisor pattern):\n" + format_attribution(agg, res.estimated))
    print(f"\nANSWER:\n{res.text}")
    if gold:
        s = score_multi(res, gold)
        print("\nSCORE:", "OK" if s["success"] else "FAIL " + "; ".join(s["reasons"]))
        for b in attribute_failure(res, s, gold):
            print("  blame:", b)
    if a.show:
        for run in res.runs:
            print(f"\n######## {run.agent} ({run.role})\n" + format_trajectory(run.records))


if __name__ == "__main__":
    main()
