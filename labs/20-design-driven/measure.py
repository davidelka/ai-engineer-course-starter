"""Exercises 1 and 3: measure the tests before and after the refactor.

    python labs/20-design-driven/measure.py --before          # legacy/tangled.py with legacy/tests
    python labs/20-design-driven/measure.py --after           # your AnswerService with after_tests/
    python labs/20-design-driven/measure.py --after --ref     # the reference AnswerService
    python labs/20-design-driven/measure.py --both

For each side it runs pytest under coverage.py with branch measurement, in a
subprocess, and reports:
  - wall time of the whole run and the slowest tests (pytest --durations)
  - line and branch coverage of the code under test ONLY: the function
    answer_question in tangled.py, or the class AnswerService (the rest of
    mine.py belongs to other exercises and would distort the number)
  - which lines were never executed

Uses coverage.py directly (`python -m coverage run --branch ...`). The
pytest-cov plugin (`pytest --cov`) wraps the same engine; either is fine.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]


def span(path: Path, name: str) -> tuple[int, int]:
    """First and last line of a top-level def/class called `name`."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name:
            return node.lineno, node.end_lineno
    raise SystemExit(f"{name} not found in {path}")


def run(label: str, tests: Path, target: Path, name: str, env_extra: dict) -> dict:
    lo, hi = span(target, name)
    with tempfile.TemporaryDirectory() as tmp:
        data, out = Path(tmp) / ".coverage", Path(tmp) / "cov.json"
        env = {**os.environ, **env_extra, "COVERAGE_FILE": str(data)}
        cmd = [sys.executable, "-m", "coverage", "run", "--branch", f"--include={target}",
               "-m", "pytest", "-q", "-p", "no:cacheprovider", "--durations=3", "--durations-min=0.05", str(tests)]
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        wall = time.perf_counter() - t0
        subprocess.run([sys.executable, "-m", "coverage", "json", "-q", "-o", str(out)], cwd=ROOT, env=env,
                       capture_output=True, text=True)
        files = json.loads(out.read_text())["files"] if out.exists() else {}
    f = next((v for k, v in files.items() if Path(k).resolve() == target.resolve()), None)
    if f is None:
        print(proc.stdout[-2000:], proc.stderr[-2000:])
        raise SystemExit(f"{label}: no coverage data for {target} (did the tests import it?)")

    def inside(line: int) -> bool:
        return lo <= line <= hi

    ex = [n for n in f["executed_lines"] if inside(n)]
    miss = [n for n in f["missing_lines"] if inside(n)]
    exb = [b for b in f.get("executed_branches", []) if inside(b[0])]
    misb = [b for b in f.get("missing_branches", []) if inside(b[0])]
    summary = (re.findall(r"^=*\s*(\d+ \w+.*in [\d.]+s.*?)\s*=*$", proc.stdout, re.M) or ["?"])[-1]
    slow = re.findall(r"^\s*([\d.]+)s (call|setup|teardown)\s+(\S+)$", proc.stdout, re.M)
    return {"label": label, "wall": wall, "summary": summary, "slow": slow,
            "lines": (len(ex), len(ex) + len(miss)), "branches": (len(exb), len(exb) + len(misb)),
            "missing": miss, "target": f"{target.relative_to(ROOT)}::{name} (lines {lo}-{hi})"}


def pct(a: tuple[int, int]) -> str:
    return f"{100 * a[0] / a[1]:.0f}% ({a[0]}/{a[1]})" if a[1] else "n/a"


def show(r: dict) -> None:
    print(f"\n== {r['label']}: {r['target']}")
    print(f"   pytest:    {r['summary']}")
    print(f"   wall time: {r['wall']:.2f} s  (including Python start-up and coverage)")
    for secs, phase, test in r["slow"][:3]:
        print(f"   slowest:   {secs}s {phase} {test.split('::')[-1]}")
    print(f"   lines:     {pct(r['lines'])}")
    print(f"   branches:  {pct(r['branches'])}")
    if r["missing"]:
        print(f"   never run: lines {', '.join(map(str, r['missing']))}")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--before", action="store_true")
    g.add_argument("--after", action="store_true")
    g.add_argument("--both", action="store_true")
    ap.add_argument("--ref", action="store_true", help="measure designkit/service.py instead of mine.py")
    a = ap.parse_args()
    results = []
    if a.before or a.both:
        results.append(run("before", LAB / "legacy" / "tests", LAB / "legacy" / "tangled.py", "answer_question", {}))
    if a.after or a.both:
        target = ROOT / "designkit" / "service.py" if a.ref else LAB / "mine.py"
        results.append(run("after", LAB / "after_tests", target, "AnswerService",
                           {"BRAIN_IMPL": "ref" if a.ref else "mine"}))
    for r in results:
        show(r)
    if len(results) == 2:
        b, f = results
        print(f"\n   speed-up: {b['wall'] / f['wall']:.1f}x wall time. Both runs pay the same start-up cost "
              "(Python, imports, coverage), so compare the 'slowest' lines too.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
