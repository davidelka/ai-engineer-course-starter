"""Which implementation runs: your mine.py functions, and (on the solutions branch) the references.

mine.py is loaded by path under the module name "f2_mine" (not "mine"), so it never collides
with the mine.py of a lab or of project F3 when several are imported in one process.

- On `main` (the course repo as you get it) there is no reference code. A milestone you have not
  written yet stops the command with MilestoneTodo, which names the milestone and the function.
- On the `solutions` branch, hebtutor/_reference.py holds the reference implementations. A TODO
  falls back to the reference (once per process, with a note on stderr), and `--reference` forces
  the references everywhere.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

PROJECT = Path(__file__).resolve().parent.parent

# function name -> milestone (README, "אבני הדרך")
MILESTONES = {
    "screen_text": 2,
    "screen_output": 2,
    "redact_for_log": 2,
    "retrieve_phrases": 3,
    "build_request": 4,
    "partial_json_field": 4,
    "validate_assessment": 5,
    "sm2_update": 6,
    "update_level": 6,
    "word_feedback": 8,
    "correction_metrics": 9,
}
NAMES = tuple(MILESTONES)
_WARNED: set[str] = set()
_FORCE_REFERENCE = False
_QUIET = False


class MilestoneTodo(NotImplementedError):
    """A milestone function in mine.py is still a TODO, and there is no reference to fall back on."""


def _todo(name: str) -> MilestoneTodo:
    return MilestoneTodo(f"milestone {MILESTONES[name]}: mine.{name} is still a TODO. Write it in "
                         f"projects/f2-hebrew-tutor/mine.py (the contract is its docstring; "
                         f"stuck? HINTS.md -> {name}).")


def reference_module():
    try:
        return importlib.import_module("hebtutor._reference")
    except ImportError:
        return None


def has_reference() -> bool:
    return reference_module() is not None


def load_mine():
    if "f2_mine" in sys.modules:
        return sys.modules["f2_mine"]
    spec = importlib.util.spec_from_file_location("f2_mine", PROJECT / "mine.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["f2_mine"] = mod
    spec.loader.exec_module(mod)
    return mod


def impl(name: str, reference: bool = False) -> Callable:
    ref = reference_module()
    if reference or _FORCE_REFERENCE:
        if ref is None:
            raise RuntimeError("--reference needs the solutions branch: hebtutor/_reference.py is not here")
        return getattr(ref, name)
    fn = getattr(load_mine(), name, None)
    if fn is None:
        if ref is None:
            raise _todo(name)
        return getattr(ref, name)

    def call(*a, **kw):
        try:
            return fn(*a, **kw)
        except MilestoneTodo:
            raise
        except NotImplementedError:
            if ref is None:
                raise _todo(name) from None
            if name not in _WARNED and not _QUIET:
                _WARNED.add(name)
                print(f"  (mine.{name} is still a TODO: using the reference)", file=sys.stderr)
            return getattr(ref, name)(*a, **kw)
    call.__name__ = name
    return call


def call(name: str, *a, **kw):
    """Module-level entry points (hebtutor.safety.screen_text, ...) go through here."""
    return impl(name)(*a, **kw)


def _lazy(name: str) -> Callable:
    def call_(*a, **kw):
        return impl(name)(*a, **kw)
    call_.__name__ = name
    return call_


@dataclass
class Hooks:
    validate_assessment: Callable = field(default_factory=lambda: _lazy("validate_assessment"))
    sm2_update: Callable = field(default_factory=lambda: _lazy("sm2_update"))
    update_level: Callable = field(default_factory=lambda: _lazy("update_level"))
    redact_for_log: Callable = field(default_factory=lambda: _lazy("redact_for_log"))
    word_feedback: Callable = field(default_factory=lambda: _lazy("word_feedback"))


def pick_hooks(reference: bool = False, *, quiet: bool = False) -> Hooks:
    """reference=True (solutions branch) makes every entry point use the references."""
    global _FORCE_REFERENCE, _QUIET
    if reference and not has_reference():
        raise RuntimeError("--reference needs the solutions branch: hebtutor/_reference.py is not here")
    _FORCE_REFERENCE, _QUIET = bool(reference), quiet or _QUIET
    return Hooks()
