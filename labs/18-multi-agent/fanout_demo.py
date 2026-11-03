"""Exercise 5: parallel fan-out research with citations.

    python labs/18-multi-agent/fanout_demo.py                          # 3 questions, 4 parallel workers, fake
    python labs/18-multi-agent/fanout_demo.py --delay 1.0 --workers 1  # simulated 1 s per model call, sequential
    python labs/18-multi-agent/fanout_demo.py --delay 1.0 --workers 4  # ... and in parallel
    python labs/18-multi-agent/fanout_demo.py --naive                  # workers take the top hit, even if stale
    python labs/18-multi-agent/fanout_demo.py --model anthropic:claude-haiku-5-5 --workers 1
    python labs/18-multi-agent/fanout_demo.py --model anthropic:claude-haiku-5-5 --workers 4
"""

from __future__ import annotations

import argparse
import json

import _lab  # noqa: F401
from _lab import RESEARCH, is_live, money
from agentkit import FakeLLM
from multikit import FanOut, SlowLLM, aggregate_runs, format_attribution, score_research
from multikit.fake import ResearchHeuristic


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="fake")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--delay", type=float, default=0.0, help="simulated seconds per model call (fake models only)")
    ap.add_argument("--naive", action="store_true")
    ap.add_argument("--ids", default="")
    a = ap.parse_args()
    if is_live(a.model):
        from llmkit import LLM
        p = w = s = LLM(a.model)
    else:
        def mk(role):
            llm = FakeLLM(ResearchHeuristic(role, naive=a.naive))
            return SlowLLM(llm, a.delay) if a.delay else llm
        p, w, s = mk("planner"), mk("worker"), mk("synth")
    fan = FanOut(p, w, s, max_workers=a.workers)
    total, ok = 0.0, 0
    qs = [json.loads(x) for x in RESEARCH.read_text(encoding="utf-8").splitlines() if x.strip()]
    if a.ids:
        qs = [q for q in qs if q["id"] in a.ids.split(",")]
    for q in qs:
        res = fan.run(q["question"], task_id=q["id"])
        sc = score_research(res, q["gold"])
        ok += sc["success"]
        total += res.cost_usd
        print(f"\n=== {q['id']}: {q['question']}")
        for sq in res.info["subquestions"]:
            print(f"  sub {sq['id']}: {sq['question']}")
        print(f"  docs read: {', '.join(res.info['docs_read'])}   cited: {', '.join(res.info['cited'])}"
              f"   unsupported: {', '.join(res.info['unsupported_citations']) or 'none'}")
        print(f"  ANSWER: {res.text}")
        print(f"  {'OK' if sc['success'] else 'FAIL'}  missing facts={sc['missing_facts']}  missing sources={sc['sources_missing']}")
        print(f"  time: total {res.elapsed_s:.2f}s, research workers (map) {res.info['map_s']:.2f}s")
        print(format_attribution(aggregate_runs(res.records), res.estimated))
    print(f"\n{ok}/{len(qs)} questions fully answered with correct citations; cost {money(total)}"
          f"{' (estimated)' if not is_live(a.model) else ''}" + ("; latency is SIMULATED (--delay)" if a.delay else ""))


if __name__ == "__main__":
    main()
