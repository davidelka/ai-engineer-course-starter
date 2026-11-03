"""Shared helpers for the lesson 27 scripts: paths, and picking your functions (mine.py)
or the reference ones (deploykit) with --reference."""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
RESULTS = LAB / "results"
_WARNED: set = set()


def pick(name: str, reference: bool):
    """Return a callable. Falls back to the reference while yours is still a TODO."""
    import deploykit.cost
    import deploykit.dockerfile
    import deploykit.terraform
    ref = {
        "rule_base_image_pinned": deploykit.dockerfile.rule_base_image_pinned,
        "rule_runs_as_non_root": deploykit.dockerfile.rule_runs_as_non_root,
        "rule_no_secrets_in_build": deploykit.dockerfile.rule_no_secrets_in_build,
        "rule_iam_least_privilege": deploykit.terraform.rule_iam_least_privilege,
        "monthly_cost": deploykit.cost.monthly_cost,
    }[name]
    if reference:
        return ref
    import mine
    fn = getattr(mine, name)

    def guarded(*a, **kw):
        try:
            return fn(*a, **kw)
        except NotImplementedError:
            if name not in _WARNED:
                _WARNED.add(name)
                print(f"  (mine.{name} is still a TODO: using the reference for this run)")
            return ref(*a, **kw)
    guarded.__name__ = name
    return guarded
