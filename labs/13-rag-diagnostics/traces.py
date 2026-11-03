"""Exercise 5: diagnose six recorded failures by hand, then check yourself.

    python labs/13-rag-diagnostics/traces.py              # show all six traces, one after the other
    python labs/13-rag-diagnostics/traces.py --t T3       # one trace
    python labs/13-rag-diagnostics/traces.py --full       # also print the full text of every prompt chunk
    python labs/13-rag-diagnostics/traces.py --check      # compare mine.TRACE_GUESSES with the classifier

The traces are in fixtures/traces.jsonl, in the same format run_diagnosis.py saves. The retrieval in
each one is real (ragkit over the Acme corpus, with the chunker and k the story names); the answers
and judge verdicts were written by hand in the style of a real model, to show one failure each.
fixtures/build_traces.py rebuilds them.
"""

from __future__ import annotations

import argparse
import json

from common import FIXTURES
from ragkit.diagnose import case_from_trace, classify, format_diagnosis


def show(t: dict, full: bool) -> None:
    print(f"\n==================== {t['trace_id']}  ({t['qid']}, {t['qtype']})")
    print(f"story: {t['story']}")
    print(f"pipeline: {t['pipeline']}; chunker {t['chunker']}; k={t['k']}; prompt {t['context_tokens']} tokens")
    print(f"question: {t['question']}")
    print(f"golden sources: {', '.join(t['source_ids']) or '(none: unanswerable)'}"
          + (f"   superseded (stale): {', '.join(t['stale_ids'])}" if t["stale_ids"] else ""))
    print(f"golden facts: {'; '.join(t['answer_facts'])}")
    for i, (q, st) in enumerate(zip(t["quotes"], t["quote_status"]), 1):
        print(f"golden quote {i} [{st}]: {q[:150]}")
    cand = list(dict.fromkeys(t["candidates"]))
    print("candidates (docs, ranked, * = golden source): " + ", ".join(
        f"{i}:{d}{'*' if d in t['source_ids'] else ''}" for i, d in enumerate(cand[:12], 1)))
    print("prompt:")
    for c in t["context"]:
        holds = [i for i, s in enumerate(t["quote_locations"], 1) if c["n"] in s]
        txt = c["text"] if full else c["text"].replace("\n", " ")[:150] + ("..." if len(c["text"]) > 150 else "")
        print(f"  [{c['n']}] {c['chunk']} ({c['effective_date']}){'  <- holds golden quote ' + str(holds) if holds else ''}")
        print(f"      {txt}")
    print(f"answer: {t['answer']}")
    print(f"citations: {t['citations']} -> cited docs {t['cited']}; abstained {t['abstained']}; "
          f"lexical fact coverage {t['fact_coverage']}")
    g = t.get("groundedness")
    if g:
        print(f"judge (claim level): {g['label']}")
        for c in g["claims"]:
            print(f"    - {c['verdict']:12s} {c['claim']}" + (f'  evidence: "{c["evidence"][:80]}"' if c.get("evidence") else ""))
    else:
        print("judge: not run on this trace")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--t", default="")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    traces = [json.loads(x) for x in (FIXTURES / "traces.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    if args.t:
        traces = [t for t in traces if t["trace_id"] == args.t]
    if not args.check:
        for t in traces:
            show(t, args.full)
        print("\nWrite your stage for each trace in mine.TRACE_GUESSES, then run with --check.")
        return
    import mine
    ok = 0
    for t in traces:
        d = classify(case_from_trace(t))
        guess = (mine.TRACE_GUESSES.get(t["trace_id"]) or "").strip()
        ok += guess == d.stage
        print(f"\n{t['trace_id']}: your guess {guess or '(empty)'}; classifier {d.stage} "
              f"{'OK' if guess == d.stage else '<-- different'}")
        print(format_diagnosis(d))
    print(f"\n{ok}/{len(traces)} match. Where you differ, decide who is right: the classifier is a procedure, "
          "and a procedure can be wrong about a case it was not designed for.")


if __name__ == "__main__":
    main()
