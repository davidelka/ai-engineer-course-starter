"""Exercise 2: lint an agent instruction file (CLAUDE.md / AGENTS.md).

    python labs/05-coding-agents/lint_instructions.py                       # agent-config/project-instructions.md
    python labs/05-coding-agents/lint_instructions.py path/to/CLAUDE.md
    python labs/05-coding-agents/lint_instructions.py --examples            # a bad and a good example side by side

Target: no errors and a score of 85 or more. The rubric is in repoguard/instructions.py.
"""

from __future__ import annotations

import os
import sys

LAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(LAB)))

from repoguard.instructions import lint  # noqa: E402

BAD = """# Project
This is the Acme access request service. Please write clean code and follow best practices.
IMPORTANT: be careful with the database. ALWAYS test properly. NEVER break things. MUST keep it simple.
CRITICAL: use common sense when adding endpoints, and write good tests as needed.
"""


def show(path: str, text: str) -> int:
    r = lint(text)
    print(f"{path}: score {r['score']}/100  {'PASSED' if r['passed'] else 'NOT PASSED'}")
    s = r["stats"]
    print(f"  lines {s['lines']}, headings {s['headings']}, bullets {s['bullets']} "
          f"({s['concrete_bullets']} concrete), test command: {'yes' if s['has_test_command'] else 'no'}, "
          f"lint command: {'yes' if s['has_lint_command'] else 'no'}")
    for f in r["findings"]:
        print(f"  {f['severity']:5} line {f['line']:<4} {f['rule']:18} {f['message']}")
    return 0 if r["passed"] and r["score"] >= 85 else 1


def main() -> None:
    if "--examples" in sys.argv:
        show("bad example", BAD)
        print()
        with open(os.path.join(LAB, "reference-config", "project-instructions.md"), encoding="utf-8") as f:
            show("reference-config/project-instructions.md", f.read())
        return
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(LAB, "agent-config", "project-instructions.md")
    with open(path, encoding="utf-8") as f:
        sys.exit(show(path, f.read()))


if __name__ == "__main__":
    main()
