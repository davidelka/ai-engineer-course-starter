"""Same generator, three oracles: weak (it runs), tests (visible tests the candidate can edit),
strong (guard + lint + pristine tests + hidden property tests). Every final candidate is
then audited the same way, so you see how many "solved" were real.

Offline (free), a scripted generator that cheats on purpose:
  python labs/07-verification-loops/compare_oracles.py
Live, Haiku 5.5 told it may edit the tests (exercise 7):
  python labs/07-verification-loops/compare_oracles.py --generator llm --allow-test-edits --include-impossible
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]

from loopkit import Budget, EvidenceLog, format_feedback, load_tasks, read_records, run_loop, should_stop, summarize  # noqa: E402
from loopkit.guard import find_tampering  # noqa: E402
from loopkit.log import format_summary  # noqa: E402
from loopkit.verifiers import TIERS, make_verifiers  # noqa: E402
from run_loop import GENERATORS, make_generator  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--generator", choices=GENERATORS, default="scripted-cheater")
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5")
    ap.add_argument("--allow-test-edits", action="store_true")
    ap.add_argument("--tiers", nargs="*", default=list(TIERS), choices=TIERS)
    ap.add_argument("--task", nargs="*", default=["all"])
    ap.add_argument("--include-impossible", action="store_true")
    ap.add_argument("--max-iters", type=int, default=4)
    ap.add_argument("--feedback", choices=("compact", "raw", "minimal"), default="compact")
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--log", type=Path, default=None)
    a = ap.parse_args(argv)

    policy, guard, formatter = should_stop, find_tampering, format_feedback
    if a.mine:
        from mine import find_tampering as guard, format_feedback as formatter, should_stop as policy  # noqa: F811
    tasks = load_tasks(LAB / "tasks", a.task, include_impossible=a.include_impossible)
    gen = make_generator(a)
    log_path = a.log or LAB / "results" / f"compare-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    log = EvidenceLog(log_path)
    labels = []
    for tier in a.tiers:
        label = f"{gen.name} | {tier}"
        labels.append(label)
        print(f"\n### oracle: {tier}")
        for t in tasks:
            res = run_loop(t, gen, make_verifiers(tier, guard=guard), budget=Budget(max_iterations=a.max_iters),
                           policy=policy, formatter=formatter, feedback_mode=a.feedback, log=log, label=label)
            flag = "   <-- FALSE PASS" if res.solved and not res.audit_passed else ""
            tamper = f", tampering seen in {res.tamper_iterations} iteration(s)" if res.tamper_iterations else ""
            print(f"  {t.id:15} {'SOLVED' if res.solved else 'not solved':10} ({res.stop_reason}, {res.iterations} it)"
                  f"  audit: {'OK' if res.audit_passed else 'FAIL'}{tamper}{flag}")
    summary = summarize([r for r in read_records([log_path]) if r.get("label") in labels])
    print("\n" + format_summary(summary))
    print("\n### the comparison")
    for label in labels:
        s = summary[label]
        print(f"  {label}: claimed {s['claimed']}/{s['tasks']}, truly solved {s['truly_solved']}, "
              f"false passes {s['false_passes']}, runs with tampering detected {s['tamper_runs']}")
    imp = [t.id for t in tasks if t.impossible]
    if imp:
        print(f"  impossible task(s) {', '.join(imp)}: any 'solved' there is cheating by definition.")
    print(f"\nlog: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
