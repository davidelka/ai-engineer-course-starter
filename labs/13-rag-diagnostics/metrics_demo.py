"""Exercise 2: stage-wise metrics (context recall/precision, citation precision/recall) on a real run.

    python labs/13-rag-diagnostics/metrics_demo.py                 # reference functions
    python labs/13-rag-diagnostics/metrics_demo.py --mine          # yours, side by side with the reference
    python labs/13-rag-diagnostics/metrics_demo.py --q q040        # one question, every number explained

Runs the lesson 9 baseline (BM25, top 5, offline extractive answerer) over the 69 answerable golden
questions, then computes for each question, from its golden source_quotes:
  context recall      quotes found whole in some prompt chunk / quotes
  context precision   rank-aware: mean of precision@k at the relevant positions
  citation precision  cited [n] whose chunk holds a golden quote / distinct cited [n]
  citation recall     quotes whose chunk was cited / quotes
and prints the mean per question type, as a list.
"""

from __future__ import annotations

import argparse
import statistics

from common import acme_qa, build_retriever, chunks, documents, make_generator, quote_status_map, run_diagnosis
from ragkit import diagnose as ref


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else float("nan")


def metrics(fns, tr):
    texts = [c["text"] for c in tr["context"]]
    locs = ref.quote_locations(tr["quotes"], texts)
    rel = ref.relevance_from_quotes(tr["quotes"], texts)
    sup = {i for s in locs for i in s}
    return {"context_recall": fns["context_recall"](tr["quotes"], texts),
            "context_precision": fns["context_precision"](rel),
            "citation_precision": fns["citation_precision"](tr["citations"], sup),
            "citation_recall": fns["citation_recall"](tr["citations"], locs)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--q", default="")
    args = ap.parse_args()
    qa = [q for q in acme_qa() if q["source_ids"]]
    cs = chunks()
    traces = run_diagnosis(qa, build_retriever("baseline", cs), make_generator("extractive"),
                           coverage=quote_status_map(documents(), cs, qa))
    names = ("context_recall", "context_precision", "citation_precision", "citation_recall")
    fns_ref = {n: getattr(ref, n) for n in names}
    fns = fns_ref
    if args.mine:
        import mine
        fns = {n: getattr(mine, n) for n in names}
    if args.q:
        tr = next(t for t in traces if t["qid"] == args.q)
        print(f"{tr['qid']} [{tr['qtype']}] {tr['question']}")
        for i, qt in enumerate(tr["quotes"], 1):
            print(f"  golden quote {i}: {qt[:110]}")
        for c in tr["context"]:
            has = [i for i, s in enumerate(tr["quote_locations"], 1) if c["n"] in s]
            print(f"  prompt {c['n']}: {c['chunk']:28s} {'holds quote ' + str(has) if has else ''}")
        print(f"  answer: {tr['answer'][:200]}\n  citations: {tr['citations']}")
        for k, v in metrics(fns, tr).items():
            print(f"  {k}: {v}")
        return
    rows = {}
    try:
        for t in traces:
            rows[t["qid"]] = (t["qtype"], metrics(fns, t), metrics(fns_ref, t))
    except NotImplementedError as e:
        raise SystemExit(f"not implemented yet: {e}")
    groups = ["ALL"] + sorted({t for t, _, _ in rows.values()})
    print(f"lesson 9 baseline, {len(rows)} answerable questions (mean over questions where the metric applies)")
    for g in groups:
        sel = [v for v in rows.values() if g == "ALL" or v[0] == g]
        parts = []
        for n in names:
            m = mean(x[1][n] for x in sel)
            r = mean(x[2][n] for x in sel)
            parts.append(f"{n} {m:.3f}" + (f" (ref {r:.3f}{' OK' if abs(m - r) < 1e-9 or (m != m and r != r) else ' DIFFERENT'})" if args.mine else ""))
        print(f"- {g} (n={len(sel)}): " + ", ".join(parts))
    none_cited = sum(1 for v in rows.values() if v[2]["citation_precision"] is None)
    print(f"questions with no citation at all (citation precision undefined, left out of the mean): {none_cited}")


if __name__ == "__main__":
    main()
