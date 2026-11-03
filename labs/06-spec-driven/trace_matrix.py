"""Exercise 3: the traceability matrix, requirement -> tests -> result.

    python labs/06-spec-driven/trace_matrix.py --reference          # markers only, reference functions
    python labs/06-spec-driven/trace_matrix.py                      # YOUR scan_req_markers and build_matrix
    python labs/06-spec-driven/trace_matrix.py --run                # also run the tests and show pass/fail
    python labs/06-spec-driven/trace_matrix.py --run --app impl --tests acceptance impl/tests
    python labs/06-spec-driven/trace_matrix.py --out results/traceability.md   # a Markdown copy for a PR

Statuses: PASSING, FAILING, UNTESTED (no test points at it), NOT RUN (tests exist, no results).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from spectools.spec import parse_spec  # noqa: E402
from spectools.trace import attach_results, junit_results, render, summary  # noqa: E402


def run_pytest(test_dir: Path, app: str) -> dict[str, str]:
    """Run one test directory with ACCESS_APP=app and return {node: outcome} from junit XML."""
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "junit.xml"
        env = {**os.environ, "ACCESS_APP": app, "PYTHONPATH": os.pathsep.join([str(ROOT), str(LAB)])}
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(test_dir), f"--junitxml={xml}"]
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        tail = (proc.stdout.strip().splitlines() or [""])[-1]
        print(f"  pytest {test_dir.relative_to(LAB)} (ACCESS_APP={app}): {tail}")
        return junit_results(xml) if xml.exists() else {}


def markdown(matrix) -> str:
    lines = ["# Traceability matrix", "", "Requirement, status, tests.", ""]
    for r in matrix.rows:
        lines.append(f"- **{r.req_id}** {r.title}: **{r.status}**")
        for t in r.tests:
            lines.append(f"  - `{t}` {r.results.get(t, '')}")
    if matrix.orphans:
        lines += ["", "## Orphan markers", ""] + [f"- {k}: {', '.join(v)}" for k, v in matrix.orphans.items()]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=str(LAB / "spec" / "access-requests.spec.md"))
    ap.add_argument("--tests", nargs="+", default=["acceptance"], help="test dirs, relative to the lab")
    ap.add_argument("--run", action="store_true", help="run the tests and attach pass/fail")
    ap.add_argument("--app", default="reference", help="ACCESS_APP for --run: reference | impl | module:factory")
    ap.add_argument("--reference", action="store_true", help="use spectools instead of mine.py")
    ap.add_argument("--out", help="also write the matrix as Markdown to this path")
    a = ap.parse_args()
    if a.reference:
        from spectools.trace import build_matrix, scan_req_markers
    else:
        from mine import build_matrix, scan_req_markers

    spec = parse_spec(Path(a.spec))
    dirs = [d if d.is_absolute() else LAB / d for d in map(Path, a.tests)]
    dirs = [d for d in dirs if d.exists()]
    try:
        matrix = build_matrix(spec, scan_req_markers(dirs))
    except NotImplementedError as e:
        print(f"{e}\n(run with --reference to see the reference matrix)")
        return 2
    if a.run:
        results: dict[str, str] = {}
        for d in dirs:
            results.update(run_pytest(d, a.app))
        attach_results(matrix, results)
    print()
    print(render(matrix))
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(summary(matrix).items())))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(markdown(matrix), encoding="utf-8")
        print(f"wrote {a.out}")
    bad = matrix.uncovered or matrix.orphans or any(r.status == "FAILING" for r in matrix.rows)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
