"""Exercise 4: query rewriting with llmkit structured output, and its effect per question type.

    python labs/12-advanced-retrieval/rewrite.py --show q040,q039,q069          # offline (replay)
    python labs/12-advanced-retrieval/rewrite.py                                 # all modes, offline
    python labs/12-advanced-retrieval/rewrite.py --llm anthropic:claude-haiku-5-5 --record
    python labs/12-advanced-retrieval/rewrite.py --base hybrid --dense e5-small --orig-weight 2

One structured call per question (ragkit.query.QueryRewriter, schema QueryRewrite) returns:
translation, variants (multi-query), subquestions (decomposition), step_back and a
hypothetical_answer (HyDE). RewritingRetriever then searches the original question plus the
rewrites of the chosen modes, and fuses all the lists with RRF.

--llm replay (default) answers from fixtures/rewrites.jsonl: HAND-WRITTEN rewrites in the style
a small model writes without knowing the corpus. They are not Claude's output; they let you see
the mechanics for free. --record with a live model appends the real rewrites to
results/rewrites_recorded.jsonl; later replay runs use them instead of the hand-written rows.
Live cost: ~700 input + ~250 output tokens per question, ~69 x $0.0002 = ~$0.015 with Haiku 5.5.

--base bm25 (default) shows the effect most clearly; --base hybrid uses BM25 + dense (RRF).
"""

from __future__ import annotations

import argparse
import json
import sys

from common import (DEFAULT_DENSE, DENSE_HELP, LLM_HELP, RESULTS, acme_qa, bm25_index, chunks,
                    confirm, dense_index, is_paid, make_llm)
from ragkit import metrics as M
from ragkit.hybrid import HybridRetriever
from ragkit.query import QueryRewriter, RewritingRetriever, queries_for

CONFIGS = [(), ("multi",), ("decompose",), ("translate",), ("stepback",), ("hyde",),
           ("multi", "decompose", "translate")]
GROUPS = ["ALL", "multi_hop", "hebrew", "cross-lingual", "version_conflict", "single_hop"]


def show(rw: QueryRewriter, qa: dict, ids: list[str]) -> None:
    for qid in ids:
        q = qa[qid]
        r = rw.rewrite(q["question"])
        v = r.value
        print(f"\n{qid} [{q['type']}] {q['question']}")
        print(f"  language: {v.language}")
        print(f"  translation: {v.translation}")
        for x in v.variants:
            print(f"  variant: {x}")
        for x in v.subquestions:
            print(f"  sub-question: {x}")
        print(f"  step_back: {v.step_back}")
        print(f"  hypothetical_answer (HyDE): {v.hypothetical_answer}")
        print(f"  queries searched with multi+decompose+translate: "
              f"{len(queries_for(q['question'], v, ('multi', 'decompose', 'translate')))}")
        print(f"  tokens {r.input_tokens}+{r.output_tokens}, ${r.cost_usd:.5f}, {r.latency_s * 1000:.0f} ms"
              + (f"  ERROR: {r.error}" if r.error else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llm", default="replay", help=LLM_HELP)
    ap.add_argument("--base", choices=["bm25", "hybrid"], default="bm25")
    ap.add_argument("--dense", default=DEFAULT_DENSE, help=DENSE_HELP + " (only with --base hybrid)")
    ap.add_argument("--show", default="", help="comma-separated question ids: print their rewrites and stop")
    ap.add_argument("--modes", default="", help="evaluate only this config, e.g. multi,decompose")
    ap.add_argument("--orig-weight", type=float, default=1.0, help="RRF weight of the original question")
    ap.add_argument("--no-translation-filter", action="store_true",
                    help="search the translation over ALL chunks, not only the other language's")
    ap.add_argument("--record", action="store_true", help="append live rewrites to results/rewrites_recorded.jsonl")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    qa_list = acme_qa()
    qa = {q["id"]: q for q in qa_list}
    answerable = [q for q in qa_list if q["source_ids"]]
    if is_paid(args.llm) and not confirm(
            f"{args.llm}: about {len(answerable) if not args.show else len(args.show.split(','))} calls, "
            f"~$0.0002 each with Haiku 5.5 (~$0.015 for all). continue?", args.yes):
        return
    llm = make_llm(args.llm)
    rec = RESULTS / "rewrites_recorded.jsonl" if args.record and args.llm != "replay" else None
    rw = QueryRewriter(llm, record_path=rec)

    if args.show:
        show(rw, qa, [s.strip() for s in args.show.split(",") if s.strip()])
        return

    cs = chunks()
    base = bm25_index(cs)
    if args.base == "hybrid":
        try:
            base = HybridRetriever({"bm25": base, "dense": dense_index(args.dense, cs)})
        except ImportError as exc:
            sys.exit(str(exc))
    configs = [tuple(m for m in args.modes.split(",") if m)] if args.modes else CONFIGS
    tables = {}
    for modes in configs:
        r = RewritingRetriever(base, rw, modes=modes, orig_weight=args.orig_weight,
                               translation_filter=not args.no_translation_filter)
        tables["+".join(modes) or "no rewrite"] = M.summarize(M.run_queries(r, qa_list, depth=10))
    print(f"\nbase retriever: {args.base}{' (' + args.dense + ')' if args.base == 'hybrid' else ''}; "
          f"rewrites from: {args.llm}; original weight {args.orig_weight}")
    for g in GROUPS:
        first = next(iter(tables.values()))
        print(f"\n{g} (n={int(first[g]['n'])})")
        for name, t in tables.items():
            d = t[g]["recall@5"] - first[g]["recall@5"]
            print(f"  - {name}: recall@5 {t[g]['recall@5']:.3f} ({d:+.3f}), MRR {t[g]['mrr']:.3f}")
    print(f"\nLLM calls made now: {rw.calls}, cost ${rw.total_cost:.4f}"
          + ("  (estimated: replay, no money spent)" if args.llm == "replay" else ""))
    if rec:
        print(f"recorded: {rec}")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"rewrite_{args.base}_{args.llm.replace(':', '_')}.json"
    out.write_text(json.dumps(tables, indent=1))
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
