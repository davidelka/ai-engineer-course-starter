"""Which implementation runs: your mine.py functions, and (on the solutions branch) the references.

mine.py is loaded BY PATH under the module name "f1_mine". The plain name "mine" is taken by every
lesson and project (M1's acmeqa imports its own `mine`), and the test suite runs all of them in one
process, so a shared name would hand one project another project's functions.

- On `main` (the course repo as you get it) there is no reference code. A milestone you have not
  written yet stops the command with MilestoneTodo, which names the milestone and the function.
- On the `solutions` branch, cbrain/_reference.py holds the reference implementations. A TODO falls
  back to the reference (once per process, with a note on stderr), and `--reference` (or
  BRAIN_REFERENCE=1) forces the references everywhere.

Company Brain also runs YOUR M1 (projects/m1-knowledge-assistant/mine.py) for the knowledge path,
so M1 has to be finished first.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import PROJECT

# function name -> milestone (README, "אבני הדרך")
MILESTONES = {
    "rule_intent": 3,
    "route_message": 3,
    "route_metrics": 3,
    "approvals_for": 4,
    "harden_route": 5,
    "screen_hits": 5,
    "spotlight_sources": 5,
    "validate_output": 5,
    "request_classification": 6,
    "request_rows": 9,
    "slo_report": 9,
}
NAMES = tuple(MILESTONES)
_WARNED: set[str] = set()
_FORCE_REFERENCE = False


class MilestoneTodo(NotImplementedError):
    """A milestone function in mine.py is still a TODO, and there is no reference to fall back on."""


def _todo(name: str) -> MilestoneTodo:
    return MilestoneTodo(f"milestone {MILESTONES[name]}: mine.{name} is still a TODO. Write it in "
                         f"projects/f1-company-brain/mine.py (the contract is its docstring; "
                         f"stuck? HINTS.md -> {name}).")


def reference_module():
    try:
        return importlib.import_module("cbrain._reference")
    except ImportError:
        return None


def has_reference() -> bool:
    return reference_module() is not None


def load_mine():
    if "f1_mine" in sys.modules:
        return sys.modules["f1_mine"]
    path = Path(os.environ.get("F1_MINE") or PROJECT / "mine.py")   # F1_MINE: check tests against another file
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("f1_mine", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["f1_mine"] = mod
    spec.loader.exec_module(mod)
    return mod


def impl(name: str, reference: bool = False, using: Optional[dict] = None) -> Callable:
    ref = reference_module()
    if reference or _FORCE_REFERENCE:
        if ref is None:
            raise RuntimeError("--reference needs the solutions branch: cbrain/_reference.py is not here")
        if using is not None:
            using[name] = "reference"
        return getattr(ref, name)
    mine = load_mine()
    fn = getattr(mine, name, None) if mine is not None else None
    if fn is None:
        if ref is None:
            raise _todo(name)
        if using is not None:
            using[name] = "reference (not in mine.py)"
        return getattr(ref, name)

    def call(*a, **kw):
        try:
            out = fn(*a, **kw)
            if using is not None:
                using[name] = "mine"
            return out
        except MilestoneTodo:
            raise
        except NotImplementedError:
            if ref is None:
                raise _todo(name) from None
            if using is not None:
                using[name] = "reference (mine is a TODO)"
            if name not in _WARNED:
                _WARNED.add(name)
                print(f"  (mine.{name} is still a TODO: using the reference)", file=sys.stderr)
            return getattr(ref, name)(*a, **kw)
    call.__name__ = name
    return call


def call(name: str, *a, **kw):
    """Module-level entry points (cbrain.router.rule_intent, cbrain.obs.slo_report, ...) go through here."""
    return impl(name)(*a, **kw)


@dataclass
class Hooks:
    rule_intent: Callable
    approvals_for: Callable
    harden_route: Callable
    request_classification: Callable
    using: dict = field(default_factory=dict)


def pick_hooks(reference: bool = False) -> Hooks:
    """The four functions the Brain object holds. Looked up lazily: a TODO only fails when called.
    reference=True also makes every module-level entry point use the references."""
    global _FORCE_REFERENCE
    if reference and not has_reference():
        raise RuntimeError("--reference needs the solutions branch: cbrain/_reference.py is not here")
    _FORCE_REFERENCE = bool(reference)
    using: dict[str, str] = {}

    def lazy(name: str) -> Callable:
        resolved: list[Callable] = []

        def call_(*a, **kw):
            if not resolved:
                resolved.append(impl(name, reference, using))
            return resolved[0](*a, **kw)
        call_.__name__ = name
        return call_

    return Hooks(**{n: lazy(n) for n in ("rule_intent", "approvals_for", "harden_route", "request_classification")},
                 using=using)
