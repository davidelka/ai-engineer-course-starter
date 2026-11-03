"""Exercise 5: calibrate the groundedness judge against 30 human-labeled answers.

    python labs/23-evaluation/calibrate.py --show-data                      # read the 30 cases and their labels first
    python labs/23-evaluation/calibrate.py                                  # heuristic judge (free)
    python labs/23-evaluation/calibrate.py --impl mine                      # kappa from YOUR mine.cohen_kappa
    python labs/23-evaluation/calibrate.py --judge anthropic:claude-haiku-5-5   # live, about $0.005
    python labs/23-evaluation/calibrate.py --judge anthropic:claude-haiku-5-5 --three-way   # keep partially_grounded

Data: labs/23-evaluation/data/human_labels.jsonl. Each line:
  {"id", "question", "contexts": [{"doc", "text"}], "answer", "human": "grounded" | "not_grounded",
   "trap": a short name of what makes the case hard, "why": the labeler's reasoning (Hebrew)}
The labels follow the groundedness rubric (evalkit/judge.py): every claim must be stated in the
context; a correct fact that is not in the context is NOT grounded; a refusal makes no claim and
is grounded; an outdated answer copied faithfully from an outdated source IS grounded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab import DATA, confirm, make_judge  # noqa: E402

from evalkit import binary_groundedness, calibrate, kappa_band  # noqa: E402

LABELS = DATA / "human_labels.jsonl"


def load() -> list[dict]:
    return [json.loads(line) for line in LABELS.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judge", default="heuristic")
    ap.add_argument("--impl", default="ref", choices=["ref", "mine"])
    ap.add_argument("--show-data", action="store_true")
    ap.add_argument("--three-way", action="store_true", help="print the judge's 3-way labels next to the binary ones")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    rows = load()
    if args.show_data:
        for r in rows:
            print(f"--- {r['id']}  human: {r['human']}  trap: {r['trap']}\nQ: {r['question']}")
            for i, c in enumerate(r["contexts"], 1):
                print(f"  [{i}] ({c['doc']}) {c['text']}")
            print(f"A: {r['answer']}\nwhy: {r['why']}\n")
        return
    if not confirm(args.judge, len(rows), 700, 300, args.yes):
        return
    judge = make_judge(args.judge)
    human, got, three, cost = [], [], [], 0.0
    for r in rows:
        res = judge.groundedness(r["question"], r["answer"], r["contexts"])
        cost += res.cost_usd
        human.append(r["human"])
        got.append(binary_groundedness(res.label) or "error")
        three.append(res.label or f"error: {res.error}")
    rep = calibrate(human, got, positive="grounded")
    kappa = rep.kappa
    if args.impl == "mine":
        import mine
        kappa = mine.cohen_kappa(human, got)
        print(f"your kappa {kappa:.3f}  (reference {rep.kappa:.3f})")
    c = rep.confusion
    g, n = "grounded", "not_grounded"
    print(f"\njudge {judge.version}   spend ${cost:.4f}")
    print(f"agreement {rep.agreement:.1%}   Cohen's kappa {kappa:.2f} ({kappa_band(kappa)})   n={rep.n}\n")
    print("confusion (human -> judge):")
    print(f"  human grounded,     judge grounded:     {c.get((g, g), 0):2d}   agree")
    print(f"  human grounded,     judge not_grounded: {c.get((g, n), 0):2d}   false fail: wastes a reviewer's time")
    print(f"  human not_grounded, judge grounded:     {c.get((n, g), 0):2d}   false pass: a regression slips through")
    print(f"  human not_grounded, judge not_grounded: {c.get((n, n), 0):2d}   agree")
    if "error" in got:
        print(f"  judge errors (no valid verdict): {got.count('error')}")
    print("\nDISAGREEMENTS (read the 'why': who is right, the judge or the label?)")
    for i in rep.disagreements:
        r = rows[i]
        extra = f" (3-way: {three[i]})" if args.three_way else ""
        print(f"- {r['id']} [{r['trap']}] human {r['human']}, judge {got[i]}{extra}\n    A: {r['answer'][:150]}\n    why: {r['why'][:200]}")
    traps: dict[str, list[bool]] = {}
    for r, h, j in zip(rows, human, got):
        traps.setdefault(r["trap"], []).append(h == j)
    print("\nagreement by trap type:")
    for t, v in sorted(traps.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        print(f"  {t:32s} {sum(v)}/{len(v)}")


if __name__ == "__main__":
    main()
