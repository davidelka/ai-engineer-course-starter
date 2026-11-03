"""Exercises 3 and 8: claim-level groundedness on five answers (fixtures/claims_examples.jsonl).

    python labs/13-rag-diagnostics/claims.py                                      # offline lexical judge, $0
    python labs/13-rag-diagnostics/claims.py --mine                               # your check_claims
    python labs/13-rag-diagnostics/claims.py --llm anthropic:claude-haiku-5-5     # live judge, ~$0.003
    python labs/13-rag-diagnostics/claims.py --nli                                # local multilingual NLI model
    python labs/13-rag-diagnostics/claims.py --show e1                            # print the prompts sent

For each example: the question, the answer, the sources (chunk ids), then every claim the judge
extracted with its verdict (supported / contradicted / not_found), the evidence it quoted, whether
that evidence really is in the source (checked in code), and the faithfulness score. Last, the
labels a careful human gave the same claims, so you can see where each judge is wrong.
"""

from __future__ import annotations

import argparse
import json
import sys

from common import FIXTURES, confirm, is_paid, make_judge
from ragkit import diagnose as ref


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llm", default="heuristic", help="heuristic (offline) | anthropic:claude-haiku-5-5 | mock:...")
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--nli", action="store_true", help=f"verify with {ref.NLI_DEFAULT} (needs transformers + torch)")
    ap.add_argument("--only", default="", help="comma list of example ids")
    ap.add_argument("--show", default="", help="print the decompose and verify prompts for one example")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    ex = [json.loads(x) for x in (FIXTURES / "claims_examples.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    if args.only:
        ex = [e for e in ex if e["id"] in args.only.split(",")]
    if args.show:
        e = next(e for e in ex if e["id"] == args.show)
        print("SYSTEM (decompose):\n" + ref.DECOMPOSE_SYSTEM + "\n\nUSER:\n" + ref.decompose_prompt(e["answer"]))
        print("\nSYSTEM (verify):\n" + ref.VERIFY_SYSTEM + "\n\nUSER (with the human's claims as an example):\n"
              + ref.verify_prompt([c for c, _ in e["human"]], [c["text"] for c in e["contexts"]]))
        return
    if is_paid(args.llm) and not confirm(f"{len(ex)} examples x 2 calls with {args.llm} (about $0.003). continue?",
                                         args.yes):
        return
    if args.llm == "heuristic" and not args.nli:
        print("note: the offline judge is LEXICAL (word overlap, numbers, negation words). It is blind to "
              "paraphrase and translation. Compare it with --llm anthropic:claude-haiku-5-5.", file=sys.stderr)
    judge = make_judge(args.llm)
    nli = ref.NLIChecker() if args.nli else None
    fn = ref.check_claims
    if args.mine:
        import mine
        fn = mine.check_claims
    total = 0.0
    for e in ex:
        texts = [c["text"] for c in e["contexts"]]
        print(f"\n=== {e['id']} ({e['qid']}) {e['question']}")
        print(f"  answer: {e['answer']}")
        print("  sources: " + ", ".join(f"[{i}] {c['chunk']}" for i, c in enumerate(e["contexts"], 1)))
        if nli is not None:
            claims = [c for c, _ in e["human"]]          # NLI only verifies; use the human's decomposition
            rep = nli.check(claims, texts)
            who = f"NLI {ref.NLI_DEFAULT}"
        else:
            try:
                rep = fn(e["answer"], texts, judge)
            except NotImplementedError:
                raise SystemExit("mine.check_claims is not implemented yet (exercise 3)")
            who = args.llm + (" (mine)" if args.mine else "")
        total += rep.cost_usd
        if rep.error:
            print(f"  ERROR: {rep.error}")
            continue
        print(f"  judge {who}: label {rep.label}, faithfulness {rep.score if rep.score is None else round(rep.score, 2)}")
        for c in rep.claims:
            ev = f' evidence: "{c.evidence[:90]}"' if c.evidence else ""
            chk = {True: " [evidence found in source]", False: " [evidence NOT in source: not counted]", None: ""}[c.evidence_verified]
            print(f"    - {c.verdict:12s} {c.claim}{chk}{ev}")
        print("  human labels: " + "; ".join(f"{v}: {c}" for c, v in e["human"]))
        print(f"  why this example: {e['lesson']}")
    print(f"\ncost: ${total:.4f}" + (" (estimated: replay priced as Haiku)" if args.llm == "heuristic" else ""))


if __name__ == "__main__":
    main()
