"""Exercise 4: LLM-as-judge for groundedness (and correctness, refusal, pairwise) with rubrics.

    python labs/23-evaluation/judge_run.py --show-rubric                      # read the rubric first
    python labs/23-evaluation/judge_run.py                                    # heuristic judge on extractive answers
    python labs/23-evaluation/judge_run.py --model anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5   # live, ~$0.03
    python labs/23-evaluation/judge_run.py --kinds groundedness,correctness,refusal --types version_conflict,unanswerable
    python labs/23-evaluation/judge_run.py --pairwise --judge heuristic-biased     # position bias, and the swap that exposes it
    python labs/23-evaluation/judge_run.py --show q003,q038                    # full verdicts (claims, evidence)

The answers come from the same cached runs as run_eval.py, so only the judge calls are new.
Judge verdicts are cached too (results/judge_cache), keyed by judge model + rubric hash + prompt.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab import CACHE, OutputCache, acme_golden, build_index, confirm, make_judge, progress, system_for  # noqa: E402

from evalkit import run_system, score_run  # noqa: E402
from evalkit.judge import RUBRICS  # noqa: E402
from evalkit.rag import judge_scorer, rag_scorer  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="extractive", help="the system that produced the answers")
    ap.add_argument("--judge", default="heuristic")
    ap.add_argument("--kinds", default="groundedness")
    ap.add_argument("--types", default="")
    ap.add_argument("--show", default="", help="comma-separated question ids to print in full")
    ap.add_argument("--show-rubric", action="store_true")
    ap.add_argument("--pairwise", action="store_true", help="compare prompt v1 vs v2 answers, with and without swap")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    kinds = tuple(args.kinds.split(","))
    if args.show_rubric:
        for k in (("pairwise",) if args.pairwise else kinds):
            print(f"===== system prompt of the {k} judge =====\n{RUBRICS[k]}\n")
        return

    ds = acme_golden()
    if args.types:
        ds = ds.filter(type=args.types)
    if not confirm(args.model, len(ds) * (2 if args.pairwise else 1), 2500, 200, args.yes):
        return
    calls = len(ds) * (4 if args.pairwise else len(kinds))
    if not confirm(args.judge, calls, 2500, 400, args.yes):
        return
    judge = make_judge(args.judge)
    idx = build_index()

    if args.pairwise:
        return pairwise(ds, idx, judge, args)

    run = run_system(system_for(args.model, "v1", 5, index=idx), ds, cache=OutputCache(CACHE), on_progress=progress)
    score_run(run, ds, [rag_scorer(), judge_scorer(judge, kinds)])
    cost = sum(r.scores.get("judge_cost_usd", 0.0) for r in run.records)
    print(f"\njudge {judge.version}\njudge spend this run: ${cost:.4f} (cached verdicts cost nothing)\n")

    if "groundedness" in kinds:
        by_type: dict[str, Counter] = defaultdict(Counter)
        for r in run.records:
            by_type[ds[r.example_id].type][r.scores.get("groundedness_label")] += 1
        print("groundedness labels by type:")
        for t, c in sorted(by_type.items()):
            print(f"  {t:17s} " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
        both = Counter((r.scores.get("grounded"), r.scores.get("answer_ok")) for r in run.records)
        print("\ngrounded vs answer_ok (the two measure different things):")
        print(f"  grounded and correct     {both[(1.0, 1.0)]}")
        print(f"  grounded but NOT correct {both[(1.0, 0.0)]}   <- faithful to the wrong source, or incomplete, or a wrong refusal")
        print(f"  NOT grounded but correct {both[(0.0, 1.0)]}   <- right answer from outside the context (or a judge error)")
        print(f"  neither                  {both[(0.0, 0.0)]}")
    for k, m in (("correctness", "judge_correct"), ("refusal", "refusal_ok")):
        if k in kinds:
            print(f"\n{m}: mean {run.mean(m):.3f} over {len(run.values(m))} answers")

    for qid in filter(None, args.show.split(",")):
        rec = run.by_id()[qid]
        ex = ds[qid]
        print(f"\n===== {qid} [{ex.type}] {ex.input['question']}\nanswer: {rec.output.get('answer')}")
        for k in kinds:
            res = getattr(judge, k)(ex.input["question"], rec.output.get("answer", ""),
                                    ex.expected.get("answer_facts", []) if k == "correctness" else rec.output.get("contexts", []))
            print(f"--- {k}: {res.label}" + (f"  (error: {res.error})" if res.error else ""))
            if res.verdict is not None:
                print(json.dumps(res.verdict.model_dump(), ensure_ascii=False, indent=2))


def pairwise(ds, idx, judge, args) -> None:
    runs = {}
    for p in ("v1", "v2"):
        r = run_system(system_for(args.model, p, 5, index=idx), ds, cache=OutputCache(CACHE), on_progress=progress)
        runs[p] = r.by_id()
    no_swap, swapped, flips = Counter(), Counter(), 0
    for ex in ds:
        a1 = runs["v1"][ex.id].output.get("answer", "")
        a2 = runs["v2"][ex.id].output.get("answer", "")
        if a1 == a2:
            continue
        ctx = runs["v1"][ex.id].output.get("contexts", [])
        facts = ex.expected.get("answer_facts") or None
        one = judge.pairwise(ex.input["question"], a1, a2, ctx, facts, swap=False)
        both = judge.pairwise(ex.input["question"], a1, a2, ctx, facts, swap=True)
        if one.label is None or both.label is None:
            continue
        no_swap[one.extra["winner"]] += 1
        swapped[both.extra["winner"]] += 1
        flips += bool(both.extra.get("position_inconsistent"))
    names = {"1": "v1 wins", "2": "v2 wins", "tie": "tie"}
    print(f"\njudge {judge.version}")
    print(f"questions where v1 and v2 answered differently: {sum(no_swap.values())}")
    print("one order only (v1 shown first): " + ", ".join(f"{names[k]} {v}" for k, v in sorted(no_swap.items())))
    print("both orders, inconsistent -> tie: " + ", ".join(f"{names[k]} {v}" for k, v in sorted(swapped.items())))
    print(f"verdicts that flipped when the order was swapped: {flips}")
    if flips:
        print("Those flips are position bias: the verdict depended on which answer was shown first.")


if __name__ == "__main__":
    main()
