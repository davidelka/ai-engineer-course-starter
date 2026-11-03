"""Exercise 5: spec drift. The code changes, the spec does not. Which net catches it?

    python labs/06-spec-driven/drift_demo.py --list
    python labs/06-spec-driven/drift_demo.py renamed_status --reference
    python labs/06-spec-driven/drift_demo.py reject_route          # YOUR find_drift and traceability
    python labs/06-spec-driven/drift_demo.py --all --reference

For one scenario it shows the patch (as a diff), then runs four nets against the patched app:
  traceability    do tests and spec still point at the same requirements?
  contract diff   does the app's own OpenAPI still match spec/openapi.yaml? (find_drift)
  contract test   Schemathesis requests generated from spec/openapi.yaml (test_acc_nfr::test_contract)
  acceptance      the example-based tests in acceptance/ (with openapi-core on every response)
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from drift.scenarios import SCENARIOS, build_app, diff  # noqa: E402
from spectools.contract import load_contract  # noqa: E402
from spectools.spec import parse_spec  # noqa: E402
from trace_matrix import run_pytest  # noqa: E402


def run(name: str, reference: bool) -> dict[str, bool]:
    if reference:
        from spectools.contract import find_drift
        from spectools.trace import build_matrix, scan_req_markers
    else:
        from mine import build_matrix, find_drift, scan_req_markers
    s = SCENARIOS[name]
    print(f"\n{'=' * 78}\nSCENARIO {name}: {s.story}\n{'=' * 78}")
    print(diff(name) or "(no code diff)")
    if s.extra_tests:
        print("The developer also added this test file (impl of the change, no spec update):")
        print("    " + s.extra_tests.strip().replace("\n", "\n    "))
    caught: dict[str, bool] = {}

    spec = parse_spec(LAB / "spec" / "access-requests.spec.md")
    with tempfile.TemporaryDirectory() as tmp:
        dirs = [LAB / "acceptance"]
        if s.extra_tests:
            (Path(tmp) / "test_change.py").write_text(s.extra_tests, encoding="utf-8")
            dirs.append(Path(tmp))
        markers: dict[str, list[str]] = {}
        for d in dirs:
            for k, v in scan_req_markers([d]).items():
                markers.setdefault(k, []).extend(v)
        m = build_matrix(spec, markers)
    orphans = {k: v for k, v in m.orphans.items()}
    caught["traceability"] = bool(orphans)
    print("\n[traceability]  " + (f"orphan ids: {orphans}" if orphans else "nothing new (REQ-10 is untested in every scenario)"))

    drifts = find_drift(load_contract(LAB / "spec" / "openapi.yaml"), build_app(name).openapi())
    caught["contract diff"] = bool(drifts)
    print("[contract diff] " + ("\n                ".join(map(str, drifts)) if drifts else "no drift"))

    results = run_pytest(LAB / "acceptance", f"drift.scenarios:{name}")
    contract_fail = sorted(k.split("::")[-1] for k, v in results.items()
                           if "test_acc_nfr" in k and "contract" in k and v == "failed")
    acc_fail = sorted(k.split("/")[-1] for k, v in results.items() if v == "failed" and "test_contract" not in k)
    caught["contract test"] = bool(contract_fail)
    caught["acceptance"] = bool(acc_fail)
    print("[contract test] " + ("FAILED" if contract_fail else "passed"))
    print("[acceptance]    " + (f"{len(acc_fail)} failed: " + ", ".join(acc_fail[:4]) + (" ..." if len(acc_fail) > 4 else "")
                                if acc_fail else "all passed"))
    print("\nCaught by: " + (", ".join(k for k, v in caught.items() if v) or "NOTHING. Which acceptance criterion is missing?"))
    return caught


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", nargs="?", choices=list(SCENARIOS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--reference", action="store_true", help="use spectools instead of mine.py")
    a = ap.parse_args()
    if a.list or not (a.scenario or a.all):
        for s in SCENARIOS.values():
            print(f"{s.name:<16} {s.story}")
        return 0
    names = list(SCENARIOS) if a.all else [a.scenario]
    try:
        table = {n: run(n, a.reference) for n in names}
    except NotImplementedError as e:
        print(f"\n{e}\n(run with --reference to use the reference functions)")
        return 2
    if len(table) > 1:
        nets = ["traceability", "contract diff", "contract test", "acceptance"]
        print(f"\n{'=' * 78}\nSUMMARY (x = caught)")
        for n, c in table.items():
            print(f"  {n:<16} " + "  ".join(f"{net}:{'x' if c[net] else '-'}" for net in nets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
