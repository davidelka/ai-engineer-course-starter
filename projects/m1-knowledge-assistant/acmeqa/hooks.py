"""Which implementation runs: your mine.py functions, and (on the solutions branch) the references.

The milestone functions live in mine.py. Every command (`python -m acmeqa ...`, the service, the
evaluation) calls them through Hooks, so the moment one of your functions works, the whole system
uses it.

- On `main` (the course repo as you get it) there is no reference code. A milestone you have not
  written yet stops the command with MilestoneTodo, which names the milestone and the function.
- On the `solutions` branch, acmeqa/_reference.py holds the reference implementations. A TODO
  falls back to the reference (once per process, with a note on stderr), and `--reference` (or
  Settings(reference=True)) forces the references everywhere.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from .config import PROJECT

# function name -> milestone (README, "אבני הדרך")
MILESTONES = {
    "build_retriever": 3,
    "pack_context": 4,
    "build_request": 5,
    "resolve_citations": 5,
    "route_question": 6,
    "answer_metrics": 8,
}

_WARNED: set[str] = set()


class MilestoneTodo(NotImplementedError):
    """A milestone function in mine.py is still a TODO, and there is no reference to fall back on."""


def reference_module():
    """acmeqa._reference on the solutions branch, None on main."""
    try:
        return importlib.import_module("acmeqa._reference")
    except ImportError:
        return None


def has_reference() -> bool:
    return reference_module() is not None


def _mine():
    if str(PROJECT) not in sys.path:
        sys.path.insert(0, str(PROJECT))
    try:
        return importlib.import_module("mine")
    except ImportError:
        return None


def _todo(name: str) -> MilestoneTodo:
    return MilestoneTodo(f"milestone {MILESTONES[name]}: mine.{name} is still a TODO. Write it in "
                         f"projects/m1-knowledge-assistant/mine.py (the contract is its docstring; "
                         f"stuck? HINTS.md -> {name}).")


def impl(name: str, reference: bool = False, using: Optional[dict] = None) -> Callable:
    """The function to call for milestone function `name`."""
    ref = reference_module()
    if reference:
        if ref is None:
            raise RuntimeError("--reference needs the solutions branch: acmeqa/_reference.py is not here")
        if using is not None:
            using[name] = "reference"
        return getattr(ref, name)
    mine = _mine()
    fn = getattr(mine, name, None) if mine is not None else None
    if fn is None:
        if ref is None:
            raise _todo(name)
        if using is not None:
            using[name] = "reference (not in mine.py)"
        return getattr(ref, name)
    if using is not None:
        using[name] = "mine"

    def call(*a, **kw):
        try:
            return fn(*a, **kw)
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


@dataclass
class Hooks:
    build_retriever: Callable
    pack_context: Callable
    build_request: Callable
    resolve_citations: Callable
    route_question: Callable
    answer_metrics: Callable
    using: dict


def pick_hooks(reference: bool = False) -> Hooks:
    """Resolve every milestone function once. Functions are looked up lazily, so a TODO only
    fails when it is actually called (the ingest command never needs your router)."""
    using: dict[str, str] = {}

    def lazy(name: str) -> Callable:
        resolved: list[Callable] = []

        def call(*a, **kw):
            if not resolved:
                resolved.append(impl(name, reference, using))
            return resolved[0](*a, **kw)
        call.__name__ = name
        return call

    return Hooks(**{n: lazy(n) for n in MILESTONES}, using=using)


def call(name: str, *a, **kw):
    """Module-level entry points (acmeqa.context.pack_context, ...) go through here."""
    return impl(name)(*a, **kw)
