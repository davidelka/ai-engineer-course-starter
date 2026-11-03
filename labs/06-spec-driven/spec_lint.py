"""Exercises 1-2: lint a spec. Uses YOUR lint_spec from mine.py unless --reference.

    python labs/06-spec-driven/spec_lint.py labs/06-spec-driven/spec/draft-vague.spec.md --reference
    python labs/06-spec-driven/spec_lint.py labs/06-spec-driven/spec/access-requests.spec.md
    python labs/06-spec-driven/spec_lint.py my-rewrite.spec.md

Exit code 1 when there is at least one error (so it can run in CI or in a hook).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]
from spectools.spec import parse_spec  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", nargs="?", default=str(LAB / "spec" / "access-requests.spec.md"))
    ap.add_argument("--reference", action="store_true", help="use spectools' lint_spec instead of mine.py")
    a = ap.parse_args()
    if a.reference:
        from spectools.lint import lint_spec
    else:
        from mine import lint_spec

    spec = parse_spec(Path(a.spec))
    try:
        findings = lint_spec(spec)
    except NotImplementedError as e:
        print(f"{e}\n(run with --reference to see the reference linter)")
        return 2
    print(f"{spec.title}: {len(spec.requirements)} requirements, ids: {', '.join(spec.ids()) or '-'}\n")
    by_req: dict = {}
    for f in findings:
        by_req.setdefault(f.req_id or "(no id)", []).append(f)
    for rid, fs in by_req.items():
        print(rid)
        for f in fs:
            print(f"  {'ERROR' if f.severity == 'error' else 'warn '}  {f.rule:<20} {f.message}")
    errors = sum(f.severity == "error" for f in findings)
    warnings = len(findings) - errors
    print(f"\n{errors} errors, {warnings} warnings" if findings else "clean: no findings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
