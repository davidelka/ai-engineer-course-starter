"""Exercises 4 and 7: diagnose every golden question for two pipelines, and compare.

    python labs/13-rag-diagnostics/run_diagnosis.py                                  # offline, $0
    python labs/13-rag-diagnostics/run_diagnosis.py --pipelines baseline --chunker fixed:100:0
    python labs/13-rag-diagnostics/run_diagnosis.py --show q040,q073
    python labs/13-rag-diagnostics/run_diagnosis.py --mine                           # your classify_failure
    python labs/13-rag-diagnostics/run_diagnosis.py --llm anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5
    python labs/13-rag-diagnostics/run_diagnosis.py --dense e5-small                 # real embeddings (lesson 10 cache)
    python labs/13-rag-diagnostics/run_diagnosis.py --rejudge traces_best_anthropic-claude-haiku-5-5_heuristic.jsonl \
        --judge anthropic:claude-haiku-5-5                                          # same answers, another judge

Pipelines (same chunks, same 79 golden questions, same answering model):
  baseline  lesson 9: BM25, top 5 chunks
  best      lesson 12: BM25 + dense with RRF, query rewrite (multi, decompose, translate), version filter
For every question: one deep search (top 50 = candidates; its first 5 = the prompt), the answer, the
citations, lexical fact coverage, and claim-level groundedness (--judge). Then ragkit.diagnose.classify
labels the root-cause stage. Printed as lists: failures by stage, by question type, the funnel, the
stage-wise metrics, and which questions the second pipeline fixed or broke.
Saved: results/traces_<pipeline>_<llm>_<judge>.jsonl (re-classify later for free) and a summary JSON.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter

from common import (DEFAULT_CHUNKER, JUDGE_HELP, LLM_HELP, PIPELINES, RESULTS, acme_qa, build_retriever, chunks,
                    confirm, documents, is_paid, make_generator, make_judge, offline_note, quote_status_map,
                    run_diagnosis, save_traces, tag)
from ragkit.diagnose import (OK, STAGES, case_from_trace, classify, format_breakdown, format_diagnosis,
                             format_funnel, funnel, trace_metrics)

METRICS = ("context_recall", "context_precision", "citation_precision", "citation_recall", "faithfulness",
           "fact_coverage")


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def format_metrics(traces, title: str) -> str:
    lines = [f"  stage-wise metrics ({title}; mean over the questions each applies to):"]
    groups = {"ALL": traces}
    for t in traces:
        groups.setdefault(t["qtype"], []).append(t)
    for g, ts in groups.items():
        if g == "unanswerable":
            continue
        ms = [trace_metrics(t) for t in ts]
        parts = []
        for m in METRICS:
            v = mean(x[m] for x in ms)
            parts.append(f"{m} {'-' if v is None else f'{v:.2f}'}")
        lines.append(f"    - {g} (n={len([t for t in ts if t['source_ids']])}): " + ", ".join(parts))
    return "\n".join(lines)


def classify_with(traces, use_mine: bool):
    if not use_mine:
        return [classify(case_from_trace(t)) for t in traces]
    import mine
    from ragkit.diagnose import Diagnosis
    out = []
    for t in traces:
        c = case_from_trace(t)
        try:
            label = mine.classify_failure(c)
        except NotImplementedError:
            sys.exit("mine.classify_failure is not implemented yet (exercise 1). Run without --mine.")
        out.append(Diagnosis(c.qid, c.qtype, label, path=["(classified by mine.classify_failure)"]))
    return out


def estimate_live_cost(n_questions: int, judge: bool) -> float:
    # Haiku 5.5: $0.10 / M input, $0.50 / M output (llmkit/pricing.py). Measured offline: the answer prompt
    # with 5 chunks is ~1,400 tokens (sources ~1,000 + system + question), the answer ~120; the two judge
    # calls cost ~$0.00037 per answered question (replay estimate), and ~85% of questions get an answer.
    gen = n_questions * (1400 * 0.10 + 120 * 0.50) / 1e6
    jud = n_questions * 0.85 * 0.00037 if judge else 0.0
    return gen + jud


def rejudge(args) -> None:
    """Same answers, another judge: how often do two judges agree, and does the diagnosis change?"""
    from pathlib import Path

    from common import load_traces
    from ragkit.diagnose import check_claims
    path = Path(args.rejudge)
    if not path.exists():
        path = RESULTS / args.rejudge
    traces = load_traces(path)
    judged = [t for t in traces if not t.get("abstained")]
    if is_paid(args.judge) and not confirm(f"{len(judged)} answers x 2 judge calls with {args.judge}: about "
                                           f"${len(judged) * 0.00037:.3f}. continue?", args.yes):
        return
    judge = make_judge(args.judge)
    before = [classify(case_from_trace(t)) for t in traces]
    agree = n = 0
    disagreements = []
    cost = 0.0
    for t in judged:
        old = (t.get("groundedness") or {}).get("label")
        rep = check_claims(t["answer"], [c["text"] for c in t["context"]], judge)
        cost += rep.cost_usd
        t["groundedness"] = rep.to_dict()
        if old is not None and rep.label is not None:
            n += 1
            same = (old == "grounded") == (rep.label == "grounded")
            agree += same
            if not same:
                disagreements.append((t["qid"], old, rep.label))
    after = [classify(case_from_trace(t)) for t in traces]
    print(f"re-judged {len(judged)} answers from {path.name} with {args.judge} (cost ${cost:.4f})")
    print(f"  agreement on grounded vs not: {agree}/{n}")
    for qid, a, b in disagreements:
        print(f"    - {qid}: before {a}, now {b}")
    changed = [(b.qid, b.stage, a.stage) for b, a in zip(before, after) if b.stage != a.stage]
    print(f"  diagnoses that changed: {len(changed)}")
    for qid, b, a in changed:
        print(f"    - {qid}: {b} -> {a}")
    out = path.with_name(path.stem + "_rejudged_" + tag(args.judge) + ".jsonl")
    save_traces(traces, out)
    print(f"  saved: {out.name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pipelines", default="baseline,best", help="comma list of: " + ", ".join(PIPELINES))
    ap.add_argument("--llm", default="extractive", help=LLM_HELP)
    ap.add_argument("--judge", default="heuristic", help=JUDGE_HELP)
    ap.add_argument("--dense", default="fake", help="fake (offline, lexical) | e5-small | bge-m3 | openai:...")
    ap.add_argument("--rewriter", default="replay", help="replay (lesson 12 fixtures) | anthropic:claude-haiku-5-5")
    ap.add_argument("--chunker", default=DEFAULT_CHUNKER)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--show", default="", help="question ids to print in full (decision path, answer, fix)")
    ap.add_argument("--mine", action="store_true", help="classify with mine.classify_failure")
    ap.add_argument("--rejudge", default="", help="a saved traces file: re-run ONLY the judge (--judge) on its "
                    "answers, compare the verdicts, and re-classify (no new answers, no retrieval)")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    if args.rejudge:
        return rejudge(args)

    qa = acme_qa()
    pipes = [p.strip() for p in args.pipelines.split(",") if p.strip()]
    paid = [s for s in (args.llm, args.judge, args.rewriter if "best" in pipes else "") if is_paid(s)]
    if paid:
        est = estimate_live_cost(len(qa), is_paid(args.judge)) * len(pipes)
        if not confirm(f"paid calls ({', '.join(sorted(set(paid)))}) for {len(qa)} questions x {len(pipes)} "
                       f"pipeline(s): about ${est:.3f} with Haiku 5.5. continue?", args.yes):
            return
    note = offline_note(args.llm, args.judge, args.dense if "best" in pipes else "",
                        args.rewriter if "best" in pipes else "")
    if note:
        print(note, file=sys.stderr)

    docs = documents()
    cs = chunks(args.chunker)
    cov = quote_status_map(docs, cs, qa)
    gen, judge = make_generator(args.llm), make_judge(args.judge)
    RESULTS.mkdir(exist_ok=True)
    runs = {}
    for p in pipes:
        r = build_retriever(p, cs, dense=args.dense, rewriter=args.rewriter)
        print(f"\n=== {p}: {PIPELINES.get(p, p)}\n    chunker {args.chunker} ({len(cs)} chunks), k={args.k}, "
              f"answers: {args.llm}, judge: {args.judge}")
        traces = run_diagnosis(qa, r, gen, k=args.k, coverage=cov, judge_llm=judge,
                               progress=(lambda i, n: print(f"\r    {i}/{n}", end="", file=sys.stderr))
                               if sys.stderr.isatty() else None)
        if sys.stderr.isatty():
            print("", file=sys.stderr)
        diags = classify_with(traces, args.mine)
        runs[p] = (traces, diags)
        print(format_breakdown(diags, p))
        print(format_funnel(diags))
        print(format_metrics(traces, p))
        cost = sum(t.get("cost_usd", 0.0) for t in traces)
        label = "estimated (replay judge priced as Haiku)" if not paid else "measured"
        print(f"  cost: ${cost:.4f} ({label})")
        name = tag("traces", p, args.llm, args.judge, args.chunker if args.chunker != DEFAULT_CHUNKER else "")
        save_traces(traces, RESULTS / f"{name}.jsonl")
        summary = {"pipeline": p, "llm": args.llm, "judge": args.judge, "chunker": args.chunker, "k": args.k,
                   "stages": dict(Counter(d.stage for d in diags)),
                   "by_type": {t: dict(Counter(d.stage for d in diags if d.qtype == t))
                               for t in sorted({d.qtype for d in diags})},
                   "funnel": funnel(diags), "labels": {d.qid: d.stage for d in diags}, "cost_usd": cost}
        (RESULTS / f"{name.replace('traces', 'summary', 1)}.json").write_text(json.dumps(summary, indent=1))
        print(f"  saved: results/{name}.jsonl")

    if len(runs) == 2:
        (pa, (ta, da)), (pb, (tb, db)) = list(runs.items())
        la, lb = {d.qid: d.stage for d in da}, {d.qid: d.stage for d in db}
        fixed = [q for q in la if la[q] != OK and lb.get(q) == OK]
        broke = [q for q in la if la[q] == OK and lb.get(q) not in (OK, None)]
        moved = [q for q in la if la[q] != OK and lb.get(q) not in (OK, None) and la[q] != lb[q]]
        print(f"\n=== {pa} -> {pb}")
        print(f"  - fixed ({len(fixed)}): " + ", ".join(f"{q} (was {la[q]})" for q in fixed))
        print(f"  - broke ({len(broke)}): " + (", ".join(f"{q} (now {lb[q]})" for q in broke) or "none"))
        print(f"  - still failing, different stage ({len(moved)}): "
              + (", ".join(f"{q} {la[q]} -> {lb[q]}" for q in moved) or "none"))
        ca, cb = Counter(la.values()), Counter(lb.values())
        print("  - per stage: " + ", ".join(f"{s} {ca.get(s, 0)}->{cb.get(s, 0)}" for s in STAGES
                                          if ca.get(s) or cb.get(s)))

    if args.show:
        for qid in args.show.split(","):
            for p, (traces, diags) in runs.items():
                for t, d in zip(traces, diags):
                    if t["qid"] == qid.strip():
                        print(f"\n--- {p}")
                        print(format_diagnosis(d, t))
                        print("   prompt: " + ", ".join(f"{c['n']}:{c['doc']}" for c in t["context"]))
                        cand = list(dict.fromkeys(t["candidates"]))
                        print("   candidates (docs, ranked): " + ", ".join(
                            f"{i}:{x}{'*' if x in t['source_ids'] else ''}" for i, x in enumerate(cand[:12], 1)))


if __name__ == "__main__":
    main()
