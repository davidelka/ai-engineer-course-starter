"""Exercise 8: score your design review against the planted problems.

    python labs/20-design-driven/check_review.py                 # designs/my_review.yaml
    python labs/20-design-driven/check_review.py --reveal        # after you are done: every problem, explained

Scoring: a finding on a section that has a planted problem counts as FOUND; it
is a full match when its checklist id is one of the accepted ones. A finding on
a section with no planted problem is a false positive (the explanation of why
that section is fine is shown). Missed problems are counted, not named, unless
you pass --reveal.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

import yaml

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT))
from designkit.review_key import FINE, FLAWS  # noqa: E402


def score(review: dict) -> dict:
    findings = review.get("findings") or []
    found, partial, false_pos, problems = {}, {}, [], []
    for i, f in enumerate(findings, 1):
        sec = str(f.get("section", "")).strip().upper()
        chk = str(f.get("checklist", "")).strip().upper()
        if not str(f.get("problem", "")).strip() or not str(f.get("fix", "")).strip():
            problems.append(f"finding {i} ({sec}): write both 'problem' and 'fix'")
        if sec in FLAWS:
            (found if chk in FLAWS[sec]["checklist"] else partial)[sec] = chk
        else:
            false_pos.append(sec)
    for sec in found:
        partial.pop(sec, None)
    return {"found": found, "partial": partial, "false_positives": false_pos, "problems": problems,
            "missed": [s for s in FLAWS if s not in found and s not in partial]}


def wrap(s: str) -> str:
    return textwrap.fill(s, 96, initial_indent="      ", subsequent_indent="      ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=str(LAB / "designs" / "my_review.yaml"))
    ap.add_argument("--reveal", action="store_true")
    a = ap.parse_args()
    review = yaml.safe_load(Path(a.path).read_text(encoding="utf-8")) or {}
    s = score(review)
    for sec in sorted(s["found"], key=lambda x: int(x[1:])):
        print(f"FOUND    {sec}  {FLAWS[sec]['title']}")
    for sec in sorted(s["partial"], key=lambda x: int(x[1:])):
        print(f"FOUND~   {sec}  right section, but {s['partial'][sec]} is not the main checklist item "
              f"(accepted: {', '.join(sorted(FLAWS[sec]['checklist']))})")
    for sec in s["false_positives"]:
        print(f"NOT A FLAW {sec}")
        if sec in FINE:
            print(wrap(FINE[sec]))
    for p in s["problems"]:
        print("INCOMPLETE", p)
    n_found = len(s["found"]) + len(s["partial"])
    print(f"\n{n_found}/{len(FLAWS)} planted problems found ({len(s['found'])} with the main checklist item), "
          f"{len(s['false_positives'])} false positive(s), {len(s['missed'])} missed.")
    if a.reveal:
        print("\nAll planted problems:")
        for sec, f in FLAWS.items():
            print(f"\n  {sec} [{', '.join(sorted(f['checklist']))}] {f['title']}")
            print(wrap("Why: " + f["why"]))
            print(wrap("Fix: " + f["fix"]))
        print("\nSections that are fine:")
        for sec, why in FINE.items():
            print(f"  {sec}: {why}")
    elif s["missed"]:
        print("Missed problems are not named. Read the doc again with the checklist, or run with --reveal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
