"""Exercise 6 (and 8): grade an implementation against SPEC-006, with no human judgment.

    python labs/06-spec-driven/grade.py --app reference     # the known-good app: everything green but REQ-10
    python labs/06-spec-driven/grade.py --app impl          # what Claude Code wrote in impl/
    python labs/06-spec-driven/grade.py --app drift.scenarios:renamed_status

Four checks, each a different net:
  1. spec lint            the spec itself is still well-formed (ids, EARS, GIVEN/WHEN/THEN)
  2. acceptance tests     acceptance/ against the app (every response also validated by openapi-core),
                          including the Schemathesis contract test (NFR-2) and the latency test (NFR-1)
  3. traceability         every requirement has a test, and every test points at a real requirement;
                          the agent's own tests in impl/tests count too, if they carry markers
  4. contract drift       the app's own OpenAPI (app.openapi()) diffed against spec/openapi.yaml

Uses the reference spectools functions (a grader should not depend on exercise code);
--mine switches to your mine.py versions.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from spectools.contract import load_contract  # noqa: E402
from spectools.spec import parse_spec  # noqa: E402
from spectools.trace import attach_results, render  # noqa: E402
from trace_matrix import run_pytest  # noqa: E402

SPEC = LAB / "spec" / "access-requests.spec.md"
CONTRACT = LAB / "spec" / "openapi.yaml"


def all_tests(d: Path) -> int:
    n = 0
    for f in list(d.rglob("test_*.py")) + list(d.rglob("*_test.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                n += 1
    return n


def load_app(target: str):
    import importlib
    target = {"reference": "reference.app:create_app", "impl": "impl.app:create_app"}.get(target, target)
    module, _, attr = target.partition(":")
    return getattr(importlib.import_module(module), attr or "create_app")()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="impl")
    ap.add_argument("--mine", action="store_true", help="use your mine.py functions")
    a = ap.parse_args()
    if a.mine:
        from mine import build_matrix, find_drift, lint_spec, scan_req_markers
    else:
        from spectools.contract import find_drift
        from spectools.lint import lint_spec
        from spectools.trace import build_matrix, scan_req_markers

    if a.app == "impl" and not (LAB / "impl" / "app.py").exists():
        print("impl/app.py does not exist yet. Exercise 6: give spec/ to Claude Code first (see IMPLEMENT_PROMPT.md).")
        return 2

    spec = parse_spec(SPEC)
    print(f"== Grading ACCESS_APP={a.app} against {spec.title}\n")

    findings = [f for f in lint_spec(spec) if f.severity == "error"]
    print(f"1. spec lint: {'clean' if not findings else f'{len(findings)} errors (fix the spec first)'}")

    print("2. tests")
    test_dirs = [LAB / "acceptance"]
    agent_tests = LAB / "impl" / "tests"
    if a.app == "impl" and agent_tests.exists():
        test_dirs.append(agent_tests)
    results: dict[str, str] = {}
    for d in test_dirs:
        results.update(run_pytest(d, a.app))

    markers: dict[str, list[str]] = {}
    for d in test_dirs:
        for k, v in scan_req_markers([d]).items():
            markers.setdefault(k, []).extend(f"{d.name}/{t}" if d != LAB / "acceptance" else t for t in v)
    # agent tests carry a "tests/" prefix so their keys stay distinct from acceptance tests
    matrix = attach_results(build_matrix(spec, markers), results)
    print("\n3. traceability")
    print("   " + render(matrix, show_tests=False).replace("\n", "\n   "))
    if agent_tests.exists() and a.app == "impl":
        marked = {t for v in scan_req_markers([agent_tests]).values() for t in v}
        print(f"   agent's own tests: {all_tests(agent_tests)} test functions, {len(marked)} carry a req marker")

    print("\n4. contract drift (app.openapi() vs spec/openapi.yaml)")
    try:
        drifts = find_drift(load_contract(CONTRACT), load_app(a.app).openapi())
    except Exception as exc:  # noqa: BLE001
        print(f"   could not build the app's OpenAPI: {exc}")
        drifts = ["unavailable"]
    for d in drifts:
        print(f"   {d}")
    if not drifts:
        print("   none")

    passing = sum(r.status == "PASSING" for r in matrix.rows)
    print(f"\n== RESULT: {passing}/{len(matrix.rows)} requirements PASSING, "
          f"{len(matrix.uncovered)} untested, {len(matrix.orphans)} orphan ids, {len(drifts)} drift items")
    ok = passing == len(matrix.rows) and not drifts and not matrix.orphans
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
