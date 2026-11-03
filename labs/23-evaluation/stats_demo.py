"""Exercise 3: is this difference real? Two RAG versions on the same 79 questions.

    python labs/23-evaluation/stats_demo.py                       # k=1 vs k=5, extractive, reference stats
    python labs/23-evaluation/stats_demo.py --impl mine           # the same with YOUR bootstrap/paired code
    python labs/23-evaluation/stats_demo.py --a-k 5 --b-model rule    # extractive vs the rule follower, both k=5
    python labs/23-evaluation/stats_demo.py --model anthropic:claude-haiku-5-5 --a-k 3 --b-k 5   # live, ~$0.04

Prints, for the headline metric answer_ok:
  1. each version's mean with its own 95% CI (the overlapping intervals that mislead people)
  2. the paired comparison (per-question differences), wins/losses, p-value
  3. McNemar's exact test on the pass/fail outcomes
  4. how big a difference this many questions can detect, and how many you would need
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab import CACHE, OutputCache, acme_golden, build_index, confirm, progress, system_for  # noqa: E402

from evalkit import run_system, score_run  # noqa: E402
from evalkit import stats as ref  # noqa: E402
from evalkit.rag import rag_scorer  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="extractive")
    ap.add_argument("--b-model", default="", help="answerer for B (default: same as --model)")
    ap.add_argument("--a-k", type=int, default=1)
    ap.add_argument("--b-k", type=int, default=5)
    ap.add_argument("--a-prompt", default="v1")
    ap.add_argument("--b-prompt", default="v1")
    ap.add_argument("--metric", default="answer_ok")
    ap.add_argument("--impl", default="ref", choices=["ref", "mine"])
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    ds = acme_golden()
    b_model = args.b_model or args.model
    if not (confirm(args.model, len(ds), 2500, 200, args.yes) and confirm(b_model, len(ds), 2500, 200, args.yes)):
        return
    idx = build_index()
    runs = []
    for model, k, p in ((args.model, args.a_k, args.a_prompt), (b_model, args.b_k, args.b_prompt)):
        s = system_for(model, p, k, index=idx)
        print(f"run {s.version}")
        r = run_system(s, ds, cache=OutputCache(CACHE), on_progress=progress)
        runs.append(score_run(r, ds, [rag_scorer(k=k)]))
    a, b = (r.values(args.metric, ds.ids()) for r in runs)

    if args.impl == "mine":
        import mine
        ca, cb = mine.bootstrap_ci(a), mine.bootstrap_ci(b)
        pr = mine.paired_compare(a, b)
        sig = pr["low"] > 0 or pr["high"] < 0
        print(f"\n1. separate CIs (yours)\n   A: {ca[0]:.3f} [{ca[1]:.3f}, {ca[2]:.3f}]"
              f"\n   B: {cb[0]:.3f} [{cb[1]:.3f}, {cb[2]:.3f}]")
        print(f"\n2. paired (yours): diff {pr['diff']:+.3f} [{pr['low']:+.3f}, {pr['high']:+.3f}] p={pr['p_value']:.3f} "
              f"better on {pr['wins']}, worse on {pr['losses']}, same on {pr['ties']} -> "
              f"{'significant' if sig else 'not significant'}")
    else:
        ca, cb = ref.bootstrap_ci(a), ref.bootstrap_ci(b)
        pr = ref.paired_compare(a, b)
        print(f"\n1. separate CIs\n   A: {ca}\n   B: {cb}")
        overlap = not (ca.high < cb.low or cb.high < ca.low)
        print(f"   the intervals {'OVERLAP' if overlap else 'do not overlap'}"
              + (": that alone does NOT mean there is no difference" if overlap else ""))
        print(f"\n2. paired: {pr}")

    pa = [v >= 1.0 for v in a]
    pb = [v >= 1.0 for v in b]
    n01 = sum(1 for x, y in zip(pa, pb) if x and not y)
    n10 = sum(1 for x, y in zip(pa, pb) if y and not x)
    print(f"\n3. McNemar exact: only A passes on {n01}, only B passes on {n10} -> p={ref.mcnemar_exact(pa, pb):.3f}")

    n = len(a)
    p0 = sum(a) / n
    disc = (n01 + n10) / n or 1 / n
    print(f"\n4. power (alpha 0.05, power 0.8, pass rate about {p0:.2f}):")
    print(f"   with n={n} two INDEPENDENT sets detect a difference of about {ref.min_detectable_diff(n, p0):.3f}")
    print(f"   with n={n} PAIRED (observed {disc:.1%} of questions flip) detect about "
          f"{ref.min_detectable_diff(n, p0, paired=True, discordant=disc):.3f}")
    for d in (0.05, 0.10):
        print(f"   to detect {d:.2f}: {ref.sample_size(d, p0)} questions per set unpaired, "
              f"{ref.sample_size(d, p0, paired=True, discordant=max(disc, d))} paired")


if __name__ == "__main__":
    main()
