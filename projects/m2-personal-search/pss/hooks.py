"""Which implementation runs: your mine.py functions, and (on the solutions branch) the references.

Every command of the project calls the milestone functions through `hooks.get(name)`, so the
moment one of your functions works, the whole tool uses it.

- On `main` (the course repo as you get it) there is no reference code. A milestone you have not
  written yet stops the command with MilestoneTodo, which names the milestone and the function.
- On the `solutions` branch, pss/_reference.py holds the reference implementations. A TODO falls
  back to the reference (with a [note]), and `--reference` (or PSS_REFERENCE=1) forces them.

mine.py is loaded from the project folder BY PATH under the module name "pss_mine", so it never
collides with another project's mine.py when the whole repo test suite runs.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Callable, Optional

PROJECT = Path(__file__).resolve().parent.parent

# function name -> milestone (README, "אבני הדרך"). Milestones 5 and 6 are optional for the rest of
# the tool: until they are written, search treats the query as plain text and nothing is folded as a
# duplicate (with a notice), so the index, the search and the evaluation already run after milestone 4.
MILESTONES = {
    "is_excluded": 2,
    "plan_sync": 3,
    "file_to_chunks": 3,
    "retrieval_row": 4,
    "parse_query": 5,
    "near_duplicate_groups": 6,
    "build_request": 7,
    "resolve_citations": 7,
    "redact_for_cloud": 8,
    "select_for_cloud": 8,
}
NAMES = tuple(MILESTONES)
_force_reference = os.environ.get("PSS_REFERENCE") == "1"
_cache: dict[str, Callable] = {}
_state: dict[str, str] = {}
_notices: list[str] = []


class MilestoneTodo(NotImplementedError):
    """A milestone function in mine.py is still a TODO, and there is no reference to fall back on."""


def _todo(name: str) -> MilestoneTodo:
    return MilestoneTodo(f"milestone {MILESTONES[name]}: mine.{name} is still a TODO. Write it in "
                         f"projects/m2-personal-search/mine.py (the contract is its docstring; "
                         f"stuck? HINTS.md -> {name}).")


def reference_module():
    try:
        return importlib.import_module("pss._reference")
    except ImportError:
        return None


def has_reference() -> bool:
    return reference_module() is not None


def force_reference(on: bool = True) -> None:
    global _force_reference
    if on and not has_reference():
        raise RuntimeError("--reference needs the solutions branch: pss/_reference.py is not here")
    _force_reference = on
    _cache.clear()
    _state.clear()


def reference(name: str) -> Optional[Callable]:
    ref = reference_module()
    return getattr(ref, name) if ref is not None else None


def load_mine():
    path = PROJECT / "mine.py"
    if not path.exists():
        return None
    if "pss_mine" in sys.modules:
        return sys.modules["pss_mine"]
    spec = importlib.util.spec_from_file_location("pss_mine", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pss_mine"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # a syntax error in mine.py: say so, do not hide it behind a TODO
        del sys.modules["pss_mine"]
        _notices.append(f"mine.py could not be imported ({type(exc).__name__}: {exc})")
        return None
    return mod


def get(name: str) -> Callable:
    if name in _cache:
        return _cache[name]
    ref = reference(name)
    if _force_reference:
        _state[name] = "reference"
        _cache[name] = ref
        return ref
    mod = load_mine()
    mine_fn = getattr(mod, name, None) if mod else None
    if mine_fn is None:
        if ref is None:
            raise _todo(name)
        _state[name] = "reference"
        _cache[name] = ref
        return ref
    _state.setdefault(name, "mine")

    def call(*a, **kw):
        try:
            out = mine_fn(*a, **kw)
            _state[name] = "mine"
            return out
        except MilestoneTodo:
            raise
        except NotImplementedError:
            if ref is None:
                raise _todo(name) from None
            if _state.get(name) != "reference":
                _notices.append(f"mine.{name} is not implemented yet: using the reference")
            _state[name] = "reference"
            return ref(*a, **kw)
    call.__name__ = name
    call.__module__ = "pss_mine"
    _cache[name] = call
    return call


def using_mine(name: str) -> bool:
    """True once your function has run (it did not raise NotImplementedError)."""
    get(name)
    return _state.get(name) == "mine"


def note(text: str) -> None:
    """A one-line notice the commands print after they run (a feature that waits for a milestone)."""
    _notices.append(text)


def notices() -> list[str]:
    out = list(dict.fromkeys(_notices))
    _notices.clear()
    return out


def call(name: str, *a, **kw):
    return get(name)(*a, **kw)
