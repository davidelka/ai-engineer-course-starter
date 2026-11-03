"""Summarize evidence logs: solved@k, false passes, cost per solved task, stop reasons.

  python labs/07-verification-loops/report.py                      # every log in results/
  python labs/07-verification-loops/report.py results/run-XYZ.jsonl
  python labs/07-verification-loops/report.py LOG --iterations     # also every iteration's evidence
  python labs/07-verification-loops/report.py LOG --task vacation_days --feedback
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]

from loopkit import format_summary, read_records, summarize  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="*", type=Path, default=[LAB / "results"])
    ap.add_argument("--iterations", action="store_true", help="print each iteration's verifiers and decision")
    ap.add_argument("--feedback", action="store_true", help="with --iterations: also the feedback text")
    ap.add_argument("--task", default=None)
    ap.add_argument("--label", default=None, help="only runs whose label contains this text")
    a = ap.parse_args(argv)
    recs = read_records(a.logs)
    if a.task:
        recs = [r for r in recs if r.get("task") == a.task]
    if a.label:
        recs = [r for r in recs if a.label in (r.get("label") or "")]
    if not recs:
        print("no records found")
        return 1
    if a.iterations:
        for r in recs:
            if r.get("type") != "iteration":
                continue
            vs = "; ".join(f"{v['verifier']}={'ok' if v['passed'] else 'FAIL'} ({v['summary']})" for v in r["verifiers"])
            print(f"[{r['label']}] {r['task']} it {r['iteration']} score {r['score']:.2f} -> {r['decision']['reason']}\n  {vs}")
            if r.get("candidate_label"):
                print(f"  candidate: {r['candidate_label']}")
            if a.feedback and r.get("feedback"):
                print("  feedback:\n" + "\n".join("    " + x for x in r["feedback"].splitlines()))
        print()
    print(format_summary(summarize(recs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
