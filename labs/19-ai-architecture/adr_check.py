"""Exercise 6: structural lint for an ADR (sections, options, numbers, honest consequences).

    python labs/19-ai-architecture/adr_check.py labs/19-ai-architecture/adr/0000-example-response-cache.md
    python labs/19-ai-architecture/adr_check.py labs/19-ai-architecture/adr/0001-company-brain-orchestration.md

It checks structure only. The reasoning is judged with adr/RUBRIC.md (by you, and in
exercise 8 by a model).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _lab  # noqa: F401  (sets sys.path)
from archkit.adr import lint_adr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("adr")
    a = ap.parse_args()
    text = Path(a.adr).read_text(encoding="utf-8")
    findings = lint_adr(text)
    for f in findings:
        print(f"  [{f.severity}] {f.where}: {f.message}")
    errors = sum(f.severity == "error" for f in findings)
    print(f"\n{errors} errors, {len(findings) - errors} warnings" if findings else "structure OK. Now read it against adr/RUBRIC.md.")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
