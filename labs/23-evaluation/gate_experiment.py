"""Exercise 6: a prompt "cleanup" (v2) that silently breaks version conflicts, and the gate that catches it.

    python labs/23-evaluation/gate_experiment.py                      # offline: the rule-following simulation
    python labs/23-evaluation/gate_experiment.py --show-diff          # which questions changed, and how
    python labs/23-evaluation/gate_experiment.py --model anthropic:claude-haiku-5-5   # live: does Haiku react the same way?
    python -m pytest -q labs/23-evaluation/ci                         # the same gate as a CI test: passes (v1)
    EVAL_CANDIDATE=v2 python -m pytest -q labs/23-evaluation/ci       # fails, and says why

The two prompts differ in one rule (see evalkit/rag.py, PROMPTS):
  v1: "- If sources disagree, prefer the one with the latest effective_date, and say that an older version said otherwise."
  v2: that line removed, and "in at most 4 sentences" softened to "briefly and helpfully".
Offline, --model rule simulates a model that obeys the version rule only when it is in the prompt
(ragkit's extractive answerer ignores prompts, so it could not show any prompt change at all).
Writes results/gate_<model>.md and .html (report with the gate verdicts).
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab import CACHE, RESULTS, OutputCache, acme_golden, build_index, confirm, progress, system_for  # noqa: E402
from gate_config import GATES  # noqa: E402

from evalkit import build_report, check_gates, run_system, score_run, to_html, to_markdown  # noqa: E402
from evalkit.rag import PROMPTS, RAG_METRICS, rag_scorer  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="rule")
    ap.add_argument("--show-diff", action="store_true", help="print the prompt diff and every changed question")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    if args.show_diff:
        print("PROMPT DIFF (v1 -> v2)")
        for line in difflib.unified_diff(PROMPTS["v1"].splitlines(), PROMPTS["v2"].splitlines(), "v1", "v2", lineterm="", n=0):
            print("  " + line)
        print()
    ds = acme_golden()
    if not confirm(args.model, 2 * len(ds), 2500, 200, args.yes):
        return
    idx = build_index()
    runs = {}
    for p in ("v1", "v2"):
        s = system_for(args.model, p, 5, index=idx)
        print(f"{p}: {s.version}")
        runs[p] = score_run(run_system(s, ds, cache=OutputCache(CACHE), on_progress=progress), ds, [rag_scorer()])
    base, cand = runs["v1"], runs["v2"]
    vc = ds.filter(type="version_conflict").ids()
    print(f"\nanswer_ok overall          v1 {base.mean('answer_ok'):.3f}  v2 {cand.mean('answer_ok'):.3f}")
    print(f"answer_ok version_conflict v1 {base.mean('answer_ok', vc):.3f}  v2 {cand.mean('answer_ok', vc):.3f}")
    print(f"stale_cited overall        v1 {base.mean('stale_cited'):.3f}  v2 {cand.mean('stale_cited'):.3f}")

    results = check_gates(cand, ds, GATES, baseline=base)
    print("\nGATE (candidate v2 vs baseline v1):")
    for r in results:
        print(f"  {r}")
    print("\nverdict:", "PASS" if all(r.passed for r in results) else "FAIL: v2 must not ship")

    if args.show_diff:
        print("\nCHANGED QUESTIONS")
        b, c = base.by_id(), cand.by_id()
        for i in ds.ids():
            if b[i].scores.get("answer_ok") != c[i].scores.get("answer_ok"):
                ex = ds[i]
                print(f"- {i} [{ex.type}] {ex.input['question'][:90]}\n"
                      f"    v1 ok={b[i].scores['answer_ok']:.0f} cited {b[i].output.get('cited_docs')}\n"
                      f"    v2 ok={c[i].scores['answer_ok']:.0f} cited {c[i].output.get('cited_docs')}  "
                      f"stale versions: {ex.expected.get('stale_ids')}\n    v2 answer: {c[i].output.get('answer', '')[:160]}")

    rep = build_report(cand, ds, RAG_METRICS, baseline=base, gate_results=results, title="Gate: prompt v2 vs v1")
    name = args.model.replace(":", "_")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"gate_{name}.md").write_text(to_markdown(rep), encoding="utf-8")
    (RESULTS / f"gate_{name}.html").write_text(to_html(rep), encoding="utf-8")
    print(f"\nreport: results/gate_{name}.md and .html")


if __name__ == "__main__":
    main()
