"""Run the verification loop on the lab's tasks and write a JSONL evidence log.

Offline (free):
  python labs/07-verification-loops/run_loop.py --generator scripted --verifier strong
  python labs/07-verification-loops/run_loop.py --generator scripted-cheater --verifier tests
  python labs/07-verification-loops/run_loop.py --generator scripted-oscillator --task business_days

Live (Haiku 5.5, a few cents):
  python labs/07-verification-loops/run_loop.py --generator llm --verifier strong --mine

Plug in YOUR stop policy, guard and feedback formatter from mine.py with --mine.
Every run appends to a log in labs/07-verification-loops/results/ (or --log PATH);
summarize logs with report.py.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]

from loopkit import (Budget, EvidenceLog, LLMGenerator, ScriptedGenerator, format_feedback, format_summary,  # noqa: E402
                     load_tasks, read_records, run_loop, should_stop, summarize)
from loopkit.guard import find_tampering  # noqa: E402
from loopkit.verifiers import TIERS, make_verifiers  # noqa: E402

GENERATORS = ("scripted", "scripted-cheater", "scripted-oscillator", "llm")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", nargs="*", default=["all"], help="task ids, or all (default)")
    ap.add_argument("--include-impossible", action="store_true", help="with 'all', also run leave_balance")
    ap.add_argument("--generator", choices=GENERATORS, default="scripted")
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5", help="llmkit spec for --generator llm")
    ap.add_argument("--allow-test-edits", action="store_true",
                    help="llm only: tell the model it may rewrite the tests (the pressure setup of exercise 7)")
    ap.add_argument("--verifier", choices=TIERS, default="strong")
    ap.add_argument("--types", action="store_true", help="add mypy to the verifiers")
    ap.add_argument("--feedback", choices=("compact", "raw", "minimal"), default="compact")
    ap.add_argument("--max-iters", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--max-cost", type=float, default=None, help="USD per task")
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--patience", type=int, default=2)
    ap.add_argument("--max-tamper", type=int, default=2)
    ap.add_argument("--flaky", type=float, default=0.0, help="inject spurious test failures with this probability")
    ap.add_argument("--reruns", type=int, default=0, help="rerun failing pytest verifiers up to N times")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--mine", action="store_true", help="use YOUR should_stop, find_tampering, format_feedback")
    ap.add_argument("--ask-every", type=int, default=0, help="human checkpoint every N iterations (and on tampering)")
    ap.add_argument("--log", type=Path, default=None)
    ap.add_argument("--label", default="")
    ap.add_argument("--show-feedback", action="store_true", help="print the feedback sent after each iteration")
    ap.add_argument("--quiet", action="store_true")
    return ap.parse_args(argv)


def make_generator(a):
    if a.generator == "llm":
        from llmkit import LLM, load_dotenv
        load_dotenv(str(LAB.parents[1] / ".env"))
        return LLMGenerator(LLM(a.model), allow_test_edits=a.allow_test_edits)
    return ScriptedGenerator({"scripted": "honest", "scripted-cheater": "cheater",
                              "scripted-oscillator": "oscillator"}[a.generator])


def ask_human(record: dict, decision) -> bool:
    print(f"\n  [checkpoint] iteration {record['iteration']}: score {record['score']}, "
          f"tampered={record['tampered']}, policy says: {decision.reason}")
    try:
        return input("  continue? [y/N] ").strip().lower().startswith("y")
    except EOFError:
        return False


def line_for(rec: dict) -> str:
    parts = []
    for v in rec["verifiers"]:
        mark = "ok" if v["passed"] else "FAIL"
        if v.get("skipped"):
            mark = "skipped"
        parts.append(f"{v['verifier']}: {mark}" + (f" ({v['summary']})" if v["kind"] == "pytest" else ""))
    est = "~" if rec.get("estimated_cost") else ""
    flags = (" TAMPER" if rec["tampered"] else "") + (f" REGRESSION x{len(rec['regressions'])}" if rec["regressions"] else "")
    return (f"  it {rec['iteration']}: score {rec['score']:.2f}{flags} | " + "; ".join(parts)
            + f" | {est}{rec['tokens_in'] + rec['tokens_out']:,} tok {est}${rec['cost_usd']:.5f}"
            + f" -> {rec['decision']['reason']}" + (f"\n      [{rec['candidate_label']}]" if rec.get("candidate_label") else ""))


def main(argv=None) -> int:
    a = parse_args(argv)
    policy, guard, formatter = should_stop, find_tampering, format_feedback
    if a.mine:
        from mine import find_tampering as guard, format_feedback as formatter, should_stop as policy  # noqa: F811
    tasks = load_tasks(LAB / "tasks", a.task, include_impossible=a.include_impossible)
    gen = make_generator(a)
    label = a.label or f"{gen.name} | {a.verifier} | {a.feedback}" + (f" | flaky={a.flaky} reruns={a.reruns}" if a.flaky or a.reruns else "")
    log_path = a.log or LAB / "results" / f"run-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    log = EvidenceLog(log_path)
    budget = Budget(max_iterations=a.max_iters, max_tokens=a.max_tokens, max_cost_usd=a.max_cost,
                    max_seconds=a.max_seconds, patience=a.patience, max_tamper=a.max_tamper)
    print(f"{label}\n{len(tasks)} task(s), budget: {budget}\nlog: {log_path}")
    for t in tasks:
        verifiers = make_verifiers(a.verifier, guard=guard, flaky=a.flaky, reruns=a.reruns, seed=a.seed,
                                   extra=("types",) if a.types else ())
        print(f"\n[{t.id}] {t.title}")

        def show(rec):
            if not a.quiet:
                print(line_for(rec))
            if a.show_feedback and rec["feedback"]:
                print("      feedback sent:\n" + "\n".join("        " + x for x in rec["feedback"].splitlines()))

        res = run_loop(t, gen, verifiers, budget=budget, policy=policy, formatter=formatter,
                       feedback_mode=a.feedback, log=log, label=label, on_iteration=show,
                       checkpoint=ask_human if a.ask_every else None, ask_every=a.ask_every)
        audit = "audit OK" if res.audit_passed else f"audit FAIL ({res.audit_summary})"
        claim = "SOLVED" if res.solved else "not solved"
        warn = "   <-- FALSE PASS" if res.solved and not res.audit_passed else ""
        print(f"  => {claim} ({res.stop_reason}) after {res.iterations} iteration(s); {audit}{warn}")
    recs = [r for r in read_records([log_path]) if r.get("label") == label]
    print("\n" + format_summary(summarize(recs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
