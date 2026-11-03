"""Exercises 4, 5 and 8: run the 15 Acme tasks and score every trajectory against its gold outcome.

    python labs/15-agent-loops/eval_tasks.py                          # reactive, fake model, free
    python labs/15-agent-loops/eval_tasks.py --mine                   # score with YOUR metrics (exercise 4)
    python labs/15-agent-loops/eval_tasks.py --modes react,plan       # exercise 5, offline
    python labs/15-agent-loops/eval_tasks.py --modes react,plan --model anthropic:claude-haiku-5-5
    python labs/15-agent-loops/eval_tasks.py --modes react,workflow   # exercise 8 (fixed workflow, no model)
    python labs/15-agent-loops/eval_tasks.py --modes workflow --model anthropic:claude-haiku-5-5   # LLM extraction
    python labs/15-agent-loops/eval_tasks.py --tasks t01,t05 --show   # print the trajectories too

Side effects are auto-approved here (the evaluation plays the human) and go to a temporary
requests store per task. Live runs stop when the total cost passes --total-budget.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import _lab  # noqa: F401
from _lab import RESULTS, TASKS, is_live, make_llm, registry
from agentkit import (Agent, Budget, format_summary, format_trajectory, load_tasks, run_workflow, score_trajectory,
                      summarize_scores)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="fake")
    ap.add_argument("--modes", default="react", help="comma list of react, plan, workflow")
    ap.add_argument("--tasks", default="", help="comma list of task ids (default: all)")
    ap.add_argument("--mine", action="store_true", help="score with mine.score_trajectory / mine.summarize_scores")
    ap.add_argument("--max-steps", type=int, default=8)
    ap.add_argument("--max-cost", type=float, default=0.01, help="per task")
    ap.add_argument("--total-budget", type=float, default=0.30, help="live runs stop past this total")
    ap.add_argument("--fault", action="append", default=[], help="tool fault for every task, e.g. lookup_employee=error:1")
    ap.add_argument("--log", default=str(RESULTS / "eval.jsonl"))
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()

    if a.mine:
        import mine
        score, summarize = mine.score_trajectory, mine.summarize_scores
    else:
        score, summarize = score_trajectory, summarize_scores
    from agentkit import parse_faults
    faults = parse_faults(a.fault)
    tasks = load_tasks(TASKS)
    if a.tasks:
        want = set(a.tasks.split(","))
        tasks = [t for t in tasks if t["id"] in want]
    live = is_live(a.model)
    if live:
        print(f"LIVE model {a.model}: {len(tasks)} tasks x {a.modes}; stops past ${a.total_budget:.2f} in total.")
    spent = 0.0
    llm = make_llm(a.model)
    for mode in [m.strip() for m in a.modes.split(",") if m.strip()]:
        scores = []
        print(f"\n######## mode={mode}  model={a.model}")
        with tempfile.TemporaryDirectory() as tmp:
            for t in tasks:
                if live and spent >= a.total_budget:
                    print(f"  total budget ${a.total_budget:.2f} reached: skipping the rest")
                    break
                reg = registry(Path(tmp) / f"{mode}-{t['id']}.db", faults)
                if mode == "workflow":
                    res = run_workflow(t["task"], reg, confirm=lambda c: True, llm=llm if live else None,
                                       log_path=a.log, task_id=t["id"])
                else:
                    agent = Agent(llm, reg, mode=mode, confirm=lambda c: True, log_path=a.log,
                                  budget=Budget(max_steps=a.max_steps, max_cost_usd=a.max_cost, max_seconds=90))
                    res = agent.run(t["task"], task_id=t["id"])
                spent += res.cost_usd
                s = score(res.records, t["gold"], t["id"])
                scores.append(s)
                mark = "OK  " if s["success"] else "FAIL"
                print(f"  {mark} {t['id']}  stop={s['stop_reason']:<12} steps={s['steps']} calls={s['tool_calls']} "
                      f"redundant={s['redundant_calls']} cost=${s['cost_usd']:.5f}"
                      + (f"   <- {'; '.join(s['reasons'])}" if s["reasons"] else ""))
                if a.show:
                    print(format_trajectory(res.records))
        if scores:
            print(format_summary(f"{mode} ({a.model})", summarize(scores), estimated=not live and a.model == "fake"))
    print(f"\ntotal cost: ${spent:.5f}{' (estimated, nothing billed)' if a.model == 'fake' else ''}   log: {a.log}")


if __name__ == "__main__":
    main()
