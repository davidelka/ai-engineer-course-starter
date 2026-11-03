"""Exercises 1 and 2: the router. Classification (structured output), the decision rule, the specialist.

    python labs/18-multi-agent/run_router.py x03                       # one task, fake models
    python labs/18-multi-agent/run_router.py x03 --max-targets 2
    python labs/18-multi-agent/run_router.py --accuracy                # routes vs gold domains, all 23 tasks
    python labs/18-multi-agent/run_router.py --accuracy --mine --threshold 0.8
    python labs/18-multi-agent/run_router.py --accuracy --model anthropic:claude-haiku-5-5   # ~23 small calls
    python labs/18-multi-agent/run_router.py "Can you sort out my thing?" --model anthropic:claude-haiku-5-5
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import _lab  # noqa: F401
from _lab import is_live, mine_or_ref, money, task_text, tasks
from agentkit import FakeLLM, format_trajectory
from multikit import build, classify, domains_of
from multikit.fake import RouterHeuristic


def accuracy(a, decide) -> None:
    llm = FakeLLM(RouterHeuristic()) if not is_live(a.model) else build("router", a.model).router_llm
    exact = clar = 0
    cost = 0.0
    ts = tasks(a.tasks)
    for t in ts:
        sr = classify(llm, t["task"])
        cost += sr.cost_usd
        d = sr.value
        choice = decide(d, threshold=a.threshold, max_targets=a.max_targets)
        gold = t["gold"].get("domains", [])
        if not gold:
            ok = choice.action == "clarify"
        elif a.max_targets == 1:
            ok = choice.action == "route" and choice.targets[0] in gold
        else:
            ok = choice.action == "route" and set(gold) <= set(choice.targets)
        exact += ok
        clar += choice.action == "clarify"
        kw = domains_of(t["task"])
        print(f"  {'OK  ' if ok else 'MISS'} {t['id']}  gold={','.join(gold) or '(clarify)':<24} model={','.join(d.routes) or '-':<24} "
              f"conf={d.confidence:.2f}  -> {choice.action} {','.join(choice.targets)}   keywords={','.join(kw) or '-'}")
    print(f"\nrouting OK {exact}/{len(ts)}   clarifying questions {clar}   classification cost {money(cost)}"
          f"{' (estimated)' if not is_live(a.model) else ''}")
    print("max_targets=1 counts a route as OK when it picks ONE of the gold domains; the other half of a cross-domain "
          "task is still lost (see the task scores in compare.py).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task", nargs="?", default="x03", help="task id or free text")
    ap.add_argument("--model", default="fake")
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--max-targets", type=int, default=1)
    ap.add_argument("--mine", action="store_true", help="use mine.decide_route")
    ap.add_argument("--accuracy", action="store_true")
    ap.add_argument("--tasks", default="")
    ap.add_argument("--show", action="store_true", help="print the specialist trajectories")
    a = ap.parse_args()
    decide, _, _ = mine_or_ref(a.mine)
    if a.accuracy:
        return accuracy(a, decide)
    tid, text, gold = task_text(a.task)
    with tempfile.TemporaryDirectory() as tmp:
        r = build("router" if a.max_targets == 1 else "router2", a.model, requests_db=Path(tmp) / "r.db",
                  confirm=lambda c: True, decide=decide, threshold=a.threshold)
        r.max_targets = a.max_targets
        res = r.run(text, task_id=tid)
    print(f"TASK {tid}: {text}\n")
    print("ROUTER DECISION (structured output):", json.dumps(res.info["decision"], ensure_ascii=False, indent=2))
    print("CHOICE (code):", res.info["choice"])
    for run in res.runs:
        print(f"  {run.agent:<10} {run.role:<11} tokens={run.tokens:>6,}  cost={money(run.cost_usd)}")
        if a.show and run.role == "worker":
            print(format_trajectory(run.records))
    print(f"\nANSWER:\n{res.text}\n\ntotal {res.tokens:,} tokens, {money(res.cost_usd)}{' (estimated)' if res.estimated else ''}")
    if gold:
        from multikit import attribute_failure, score_multi
        s = score_multi(res, gold)
        print("SCORE:", "OK" if s["success"] else "FAIL " + "; ".join(s["reasons"]))
        for b in attribute_failure(res, s, gold):
            print("  blame:", b)


if __name__ == "__main__":
    main()
