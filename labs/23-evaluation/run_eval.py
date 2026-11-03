"""Exercises 1-2: an evalkit run of the lesson-9 RAG baseline over the 79-question golden set.

    python labs/23-evaluation/run_eval.py                                   # free: extractive
    python labs/23-evaluation/run_eval.py                                   # again: all from cache
    python labs/23-evaluation/run_eval.py --metrics mine                    # score with YOUR mine.py
    python labs/23-evaluation/run_eval.py --model anthropic:claude-haiku-5-5   # live, about $0.02
    python labs/23-evaluation/run_eval.py --model mock:mock-model           # plumbing (python -m mockllm)
    python labs/23-evaluation/run_eval.py --types version_conflict,numeric --show-failures

Pipeline: dataset (versioned) -> system (versioned) -> outputs (cached by version + input) ->
metrics -> report. Writes results/run_<name>.jsonl, results/report_<name>.md and .html.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab import CACHE, RESULTS, OutputCache, acme_golden, confirm, progress, system_for  # noqa: E402

from evalkit import build_report, run_system, score_run, to_html, to_markdown  # noqa: E402
from evalkit.rag import RAG_METRICS, rag_scorer  # noqa: E402


def scorer_for(which: str):
    if which == "mine":
        import mine
        return rag_scorer(mine.fact_coverage, mine.citation_scores)
    return rag_scorer()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="extractive", help="extractive | rule | mock:mock-model | anthropic:claude-haiku-5-5")
    ap.add_argument("--prompt", default="v1", choices=["v1", "v2"])
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--types", default="", help="comma-separated question types")
    ap.add_argument("--metrics", default="ref", choices=["ref", "mine"])
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--show-failures", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    ds = acme_golden()
    if args.types:
        ds = ds.filter(type=args.types)
    print(f"dataset {ds.summary()}")
    system = system_for(args.model, args.prompt, args.k)
    print(f"system  {system.version}")
    if not confirm(args.model, len(ds), 2500, 200, args.yes):
        return
    cache = None if args.no_cache else OutputCache(CACHE)
    run = run_system(system, ds, cache=cache, on_progress=progress)
    score_run(run, ds, [scorer_for(args.metrics)])

    print(f"\n{len(run.records)} records, {run.cached_count} from cache, {len(run.errors)} errors, "
          f"new spend ${run.cost_usd:.4f}")
    rep = build_report(run, ds, RAG_METRICS, title=f"RAG eval: {args.model} prompt={args.prompt} k={args.k}")
    print("\noverall (95% bootstrap CI):")
    for m, ci in rep.overall.items():
        print(f"  {m:15s} " + ("-" if ci is None else f"{ci.estimate:.3f}  [{ci.low:.3f}, {ci.high:.3f}]  n={ci.n}"))
    print("\nby type (answer_ok · fact_coverage · stale_cited · recall@5):")
    for t, row in rep.slices.items():
        f = lambda m: "-" if row[m][0] is None else f"{row[m][0]:.2f}"  # noqa: E731
        print(f"  {t:17s} n={row['answer_ok'][1]:2d}  ok {f('answer_ok')}  facts {f('fact_coverage')}  "
              f"stale {f('stale_cited')}  r@5 {f('recall@5')}")
    if args.show_failures:
        print("\nFAILURES (answer_ok = 0)")
        for fl in rep.failures:
            print(f"- {fl['id']} [{fl['type']}] {fl['question'][:90]}\n    answer: {fl['answer'][:170]}\n"
                  f"    reference: {fl['reference'][:170]}")

    name = f"{args.model.replace(':', '_')}_{args.prompt}_k{args.k}" + (f"_{args.types.replace(',', '+')}" if args.types else "")
    RESULTS.mkdir(exist_ok=True)
    run.save(RESULTS / f"run_{name}.jsonl")
    (RESULTS / f"report_{name}.md").write_text(to_markdown(rep), encoding="utf-8")
    (RESULTS / f"report_{name}.html").write_text(to_html(rep), encoding="utf-8")
    print(f"\nrun:    results/run_{name}.jsonl\nreport: results/report_{name}.md  and  .html")


if __name__ == "__main__":
    main()
