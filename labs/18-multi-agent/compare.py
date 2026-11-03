"""Exercise 6: single agent vs router vs supervisor (and handoff) on the same 23 tasks.

    python labs/18-multi-agent/compare.py                                   # fake models, free
    python labs/18-multi-agent/compare.py --mine                            # YOUR decide_route + aggregate_runs
    python labs/18-multi-agent/compare.py --patterns single,router,router2,supervisor,handoff
    python labs/18-multi-agent/compare.py --tasks x0* --show-failures
    python labs/18-multi-agent/compare.py --model anthropic:claude-haiku-5-5   # live: stops past --total-budget ($0.40)

Every task gets fresh agents and a fresh requests store; side effects are auto-approved (the
evaluation plays the human). Scores use agentkit.score_trajectory on the merged multi-agent
trajectory (same gold as lesson 15). Results go to results/compare.jsonl.
"""

from __future__ import annotations

import argparse
import json

import _lab  # noqa: F401
from _lab import RESULTS, is_live, mine_or_ref, money, tasks
from multikit import format_attribution, run_set


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="fake")
    ap.add_argument("--patterns", default="single,router,supervisor")
    ap.add_argument("--tasks", default="")
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--total-budget", type=float, default=0.40)
    ap.add_argument("--show-failures", action="store_true")
    ap.add_argument("--log", default=str(RESULTS / "compare.jsonl"))
    a = ap.parse_args()
    decide, _, aggregate = mine_or_ref(a.mine)
    ts = tasks(a.tasks)
    live = is_live(a.model)
    if live:
        print(f"LIVE {a.model}: {len(ts)} tasks x {a.patterns}; stops past ${a.total_budget:.2f}.")
    spent = [0.0]
    summary = []
    for p in [x.strip() for x in a.patterns.split(",") if x.strip()]:
        rs = run_set(p, ts, a.model, decide=decide, log_path=a.log, budget_usd=a.total_budget if live else None,
                     spent=spent)
        if not rs:
            print(f"\n== {p}: skipped (budget)")
            continue
        print(f"\n######## {p}  ({a.model})")
        for t, res, s in rs:
            mark = "OK  " if s["success"] else "FAIL"
            print(f"  {mark} {t['id']}  agents={s['agents']} runs={s['agent_runs']} calls={s['tool_calls']:<2} "
                  f"tokens={s['tokens']:>6,} {money(s['cost_usd'])} {s['elapsed_s']:.2f}s"
                  + (f"   <- {'; '.join(s['blame'] or s['reasons'])}" if not s["success"] and a.show_failures else ""))
        recs = [r for _, res, _ in rs for r in res.records]
        agg = aggregate(recs)
        n = len(rs)
        ok = sum(s["success"] for _, _, s in rs)
        x = [s for t, _, s in rs if t["id"].startswith("x")]
        line = {"pattern": p, "success": ok, "tasks": n, "cross_ok": sum(s["success"] for s in x), "cross": len(x),
                "tokens": agg["total_tokens"], "cost": agg["total_cost_usd"],
                "latency": sum(s["elapsed_s"] for _, _, s in rs) / n, "coord": agg["coordination_share"]}
        summary.append(line)
        print(f"== {p}: success {ok}/{n} (new cross-domain {line['cross_ok']}/{line['cross']})   tokens "
              f"{agg['total_tokens']:,}   cost {money(agg['total_cost_usd'])}   mean latency {line['latency']:.2f}s")
        print(format_attribution(agg, not live))
        blames = {}
        for _, _, s in rs:
            for b in s["blame"]:
                who = b.split(":")[0]
                blames[who] = blames.get(who, 0) + 1
        if blames:
            print("  failure attribution: " + ", ".join(f"{k}={v}" for k, v in sorted(blames.items())))
    print("\n== SUMMARY")
    base = next((s for s in summary if s["pattern"] == "single"), None)
    for s in summary:
        rel = f"  x{s['tokens'] / base['tokens']:.2f} tokens vs single" if base and base["tokens"] else ""
        print(f"  {s['pattern']:<11} success {s['success']}/{s['tasks']}  cross {s['cross_ok']}/{s['cross']}  "
              f"tokens {s['tokens']:>8,}  cost {money(s['cost'])}  latency {s['latency']:.2f}s  coordination "
              f"{s['coord']:.0%}{rel}")
    print(f"\ntotal cost {money(spent[0])}{' (estimated, nothing billed)' if not live else ''}   log: {a.log}")
    (RESULTS).mkdir(exist_ok=True)
    (RESULTS / "compare_summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
