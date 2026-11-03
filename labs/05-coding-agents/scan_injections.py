"""Exercise 7: scan a repository for text that tries to instruct the agent.

    python labs/05-coding-agents/scan_injections.py                       # sample-service, your mine.find_injections
    python labs/05-coding-agents/scan_injections.py --impl reference
    python labs/05-coding-agents/scan_injections.py --path ~/projects/some-repo

Instruction files (CLAUDE.md, AGENTS.md, SKILL.md, .claude/) are skipped on purpose: they are
the legitimate channel for instructions. Everything else that talks to "the AI" is suspect.
"""

from __future__ import annotations

import argparse
import os
import sys

LAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(LAB)))
sys.path.insert(0, LAB)

from repoguard import injection  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default=os.path.join(LAB, "sample-service"))
    ap.add_argument("--impl", choices=["mine", "reference"], default="mine")
    a = ap.parse_args()
    if a.impl == "mine":
        import mine

        injection.find_injections = mine.find_injections  # scan_tree looks the function up at call time
    hits = injection.scan_tree(os.path.expanduser(a.path))
    if not hits:
        print("no suspicious lines found")
        return
    for h in hits:
        print(f"{h['path']}:{h['line']}  {h['kind']:16} {h['text'][:110]}")
    print(f"\n{len(hits)} hit(s) in {len({h['path'] for h in hits})} file(s)")


if __name__ == "__main__":
    main()
