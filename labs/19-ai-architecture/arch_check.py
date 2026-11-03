"""Exercises 3, 4 and 7: run the architecture rules on a spec, like a linter.

    python labs/19-ai-architecture/arch_check.py labs/19-ai-architecture/specs/company_brain.arch.yaml
    python labs/19-ai-architecture/arch_check.py <spec> --reference

Rules 1-3 come from mine.py (rule 1 is the worked example), rules 4-5 from archkit.rules.
Exit code 1 when there is at least one error, so it can run in CI.
"""

from __future__ import annotations

import argparse
from collections import Counter

from _lab import load, pick

from archkit.rules import rule_observability, rule_write_tools_approved  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--reference", action="store_true")
    a = ap.parse_args()
    spec = load(a.spec)
    rules = [pick("rule_external_input_guarded", a.reference)[0], pick("rule_llm_resilience", a.reference)[0],
             pick("rule_pii_classified", a.reference)[0], rule_write_tools_approved, rule_observability]
    findings = [f for r in rules for f in r(spec)]
    print(f"# {spec.system}: {len(spec.components)} components, {len(spec.flows)} flows, "
          f"{len(spec.boundaries)} boundaries\n")
    for f in sorted(findings, key=lambda f: (f.severity != "error", f.rule, f.where)):
        print(f"  {f}")
    c = Counter(f.severity for f in findings)
    print(f"\n{c['error']} errors, {c['warning']} warnings")
    if not findings:
        print("clean.")
    raise SystemExit(1 if c["error"] else 0)


if __name__ == "__main__":
    main()
