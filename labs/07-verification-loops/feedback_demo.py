"""Exercise 5, part 2: raw pytest output next to YOUR compact feedback, with sizes.

  python labs/07-verification-loops/feedback_demo.py                    # vacation_days starter
  python labs/07-verification-loops/feedback_demo.py --task parse_duration --hidden
  python labs/07-verification-loops/feedback_demo.py --reference        # loopkit's formatter
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]

from loopkit import load_tasks  # noqa: E402
from loopkit.feedback import format_feedback as ref_format  # noqa: E402
from loopkit.verifiers import PytestVerifier  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="vacation_days")
    ap.add_argument("--source", default="starter/solution.py", help="file inside the task folder to test")
    ap.add_argument("--hidden", action="store_true", help="run the hidden checks instead of the visible tests")
    ap.add_argument("--reference", action="store_true")
    a = ap.parse_args(argv)
    fmt = ref_format
    if not a.reference:
        from mine import format_feedback as fmt
    t = load_tasks(LAB / "tasks", [a.task], include_impossible=True)[0]
    files = {**t.starter_files(), t.module: t.read(a.source)}
    v = PytestVerifier("hidden_tests" if a.hidden else "visible_tests", sets=("hidden",) if a.hidden else ("tests",),
                       clean_room=True)
    ev = v.verify(t, files)
    compact = fmt(ev.output)
    print("=" * 30, "RAW pytest output", "=" * 30)
    print(ev.output)
    print("=" * 30, "COMPACT feedback", "=" * 30)
    print(compact)
    print("=" * 78)
    print(f"raw: {len(ev.output):,} chars (~{len(ev.output) // 4:,} tokens)   "
          f"compact: {len(compact):,} chars (~{len(compact) // 4:,} tokens)   "
          f"ratio: {len(compact) / max(1, len(ev.output)):.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
