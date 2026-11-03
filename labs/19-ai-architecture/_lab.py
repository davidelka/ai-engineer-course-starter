"""Shared helpers for the lesson 19 scripts: paths, spec loading, and picking
your functions (mine.py) or the reference ones (archkit) with --reference."""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
RESULTS = LAB / "results"

from archkit import SpecError, load_spec  # noqa: E402


def load(path: str):
    try:
        return load_spec(path)
    except SpecError as exc:
        print(f"spec error in {path}:\n{exc}")
        raise SystemExit(2)


def pick(name: str, reference: bool):
    """Return (function, source). Falls back to the reference when yours is still a TODO."""
    import archkit.cost
    import archkit.latency
    import archkit.mermaid
    import archkit.rules
    ref = {
        "request_cost": archkit.cost.request_cost, "monthly_cost": archkit.cost.monthly_cost,
        "latency_budget": archkit.latency.latency_budget,
        "rule_external_input_guarded": archkit.rules.rule_external_input_guarded,
        "rule_llm_resilience": archkit.rules.rule_llm_resilience,
        "rule_pii_classified": archkit.rules.rule_pii_classified,
        "to_mermaid": archkit.mermaid.to_mermaid,
    }[name]
    if reference:
        return ref, "reference"
    import mine
    fn = getattr(mine, name)

    warned = []

    def guarded(*a, **kw):
        try:
            return fn(*a, **kw)
        except NotImplementedError:
            if not warned:
                warned.append(1)
                print(f"  (mine.{name} is still a TODO: using the reference for this run)")
            return ref(*a, **kw)
    return guarded, "mine.py"
