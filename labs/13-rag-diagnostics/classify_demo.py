"""Exercise 1: the stage classifier on 20 constructed cases (fixtures/cases.jsonl), then on real runs.

    python labs/13-rag-diagnostics/classify_demo.py            # reference classifier, with the decision path
    python labs/13-rag-diagnostics/classify_demo.py --mine     # yours next to the expected label
    python labs/13-rag-diagnostics/classify_demo.py --case c09_lost_in_middle

Each case lists the golden data and what the pipeline did (doc ids only, so it fits on a screen),
the expected root cause and why. A wrong label from your classifier prints the reference's decision
path, so you can see which question in the procedure you answered differently.
"""

from __future__ import annotations

import argparse
import json

from common import FIXTURES
from ragkit.diagnose import FIXES, Case, classify


def show_case(c: Case) -> str:
    def short(xs):
        xs = list(dict.fromkeys(xs)) if len(xs) > 6 else list(xs)
        return ", ".join(xs[:8]) + (f", ... ({len(xs)} docs)" if len(xs) > 8 else "") if xs else "-"
    lines = [f"    sources {short(c.source_ids)} | quote_status {c.quote_status or '-'} | stale {short(c.stale_ids)}",
             f"    candidates: {short(c.candidates)}",
             f"    prompt (k={len(c.context)}, {c.context_tokens} tokens): {short(c.context)}; evidence at {c.evidence_positions or '-'}",
             f"    answer: {c.answer[:110]}",
             f"    abstained {c.abstained}, cited {short(c.cited)}, invalid [n] {c.invalid_citations}, "
             f"fact_coverage {c.fact_coverage}, grounded {c.grounded}"]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--case", default="")
    args = ap.parse_args()
    rows = [json.loads(x) for x in (FIXTURES / "cases.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    if args.case:
        rows = [r for r in rows if r["name"] == args.case]
    ok = 0
    for r in rows:
        case = Case(**r["case"])
        ref = classify(case)
        line = f"\n{r['name']}: expected {r['expected']}"
        if args.mine:
            import mine
            try:
                got = mine.classify_failure(case)
            except NotImplementedError:
                raise SystemExit("mine.classify_failure is not implemented yet")
            ok += got == r["expected"]
            line += f", yours {got} {'OK' if got == r['expected'] else '<-- DIFFERENT'}"
        print(line)
        print(f"    why: {r['why']}")
        print(show_case(case))
        if not args.mine or got != r["expected"]:
            for p in ref.path:
                print(f"     . {p}")
            if ref.fix:
                print(f"     fix (lesson {ref.fix.lesson}): {ref.fix.action}")
    if args.mine:
        print(f"\n{ok}/{len(rows)} match")


if __name__ == "__main__":
    main()
