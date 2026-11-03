"""Your mine.py functions where implemented, the references elsewhere (same idea as M1 and F2/F3).

mine.py is loaded BY PATH under the module name "f1_mine". The plain name "mine" is taken by every
lesson and project (M1's acmeqa imports its own `mine`), and the test suite runs all of them in one
process, so a shared name would hand one project another project's functions.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import PROJECT

_WARNED: set[str] = set()
NAMES = ("rule_intent", "approvals_for", "harden_route", "request_classification")


def _refs() -> dict[str, Callable]:
    from .guards import harden_route, request_classification
    from .router import rule_intent
    from .workflow import approvals_for
    return {"rule_intent": rule_intent, "approvals_for": approvals_for, "harden_route": harden_route,
            "request_classification": request_classification}


def load_mine():
    if "f1_mine" in sys.modules:
        return sys.modules["f1_mine"]
    import os
    path = Path(os.environ.get("F1_MINE") or PROJECT / "mine.py")   # F1_MINE: check tests against another file
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("f1_mine", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["f1_mine"] = mod
    spec.loader.exec_module(mod)
    return mod


@dataclass
class Hooks:
    rule_intent: Callable
    approvals_for: Callable
    harden_route: Callable
    request_classification: Callable
    using: dict = field(default_factory=dict)


def pick_hooks(reference: bool = False) -> Hooks:
    refs = _refs()
    if reference:
        return Hooks(**refs, using={k: "reference" for k in refs})
    mine = load_mine()
    using: dict[str, str] = {}

    def guarded(name: str) -> Callable:
        fn, ref = getattr(mine, name, None) if mine else None, refs[name]
        if fn is None:
            using[name] = "reference"
            return ref
        using[name] = "mine"

        def call(*a, **kw):
            try:
                return fn(*a, **kw)
            except NotImplementedError:
                using[name] = "reference (mine is a TODO)"
                if name not in _WARNED:
                    _WARNED.add(name)
                    print(f"  (mine.{name} is still a TODO: using the reference)", file=sys.stderr)
                return ref(*a, **kw)
        return call

    return Hooks(**{n: guarded(n) for n in NAMES}, using=using)
