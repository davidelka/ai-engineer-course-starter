"""Which implementation runs: yours (mine.py) or the reference.

Every command of the project calls these five functions through `hooks.get(name)`. A function
in mine.py is used as soon as it stops raising NotImplementedError (checked once, with a tiny
probe call); until then the reference runs, and a one-line notice says so. `--reference` on
the command line (or PSS_REFERENCE=1) forces the references.

mine.py is loaded from the project folder BY PATH under the module name "pss_mine", so it never
collides with another project's mine.py when the whole repo test suite runs.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Callable

PROJECT = Path(__file__).resolve().parent.parent
NAMES = ("is_excluded", "plan_sync", "parse_query", "near_duplicate_groups", "redact_for_cloud")
_force_reference = os.environ.get("PSS_REFERENCE") == "1"
_cache: dict[str, Callable] = {}
_notices: list[str] = []


def force_reference(on: bool = True) -> None:
    global _force_reference
    _force_reference = on
    _cache.clear()


def reference(name: str) -> Callable:
    if name == "is_excluded":
        from .scan import is_excluded
        return is_excluded
    if name == "plan_sync":
        from .manifest import plan_sync
        return plan_sync
    if name == "parse_query":
        from .query import parse_query
        return parse_query
    if name == "near_duplicate_groups":
        from .dedup import near_duplicate_groups
        return near_duplicate_groups
    if name == "redact_for_cloud":
        from .privacy import redact_for_cloud
        return redact_for_cloud
    raise KeyError(name)


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
    except Exception as exc:  # a syntax error in mine.py must not break the tool
        del sys.modules["pss_mine"]
        _notices.append(f"mine.py could not be imported ({type(exc).__name__}: {exc}); using the references")
        return None
    return mod


PROBES = {
    "is_excluded": lambda f: f("a/b.txt", ["*.md"]),
    "plan_sync": lambda f: f({}, {}, lambda _id: ""),
    "parse_query": lambda f: f("hello"),
    "near_duplicate_groups": lambda f: f({}),
    "redact_for_cloud": lambda f: f("hello"),
}


def get(name: str) -> Callable:
    if name in _cache:
        return _cache[name]
    fn = reference(name)
    if not _force_reference:
        mod = load_mine()
        mine_fn = getattr(mod, name, None) if mod else None
        if mine_fn is not None:
            try:
                PROBES[name](mine_fn)
                fn = mine_fn
            except NotImplementedError:
                _notices.append(f"mine.{name} is not implemented yet: using the reference")
            except Exception as exc:  # implemented but broken on the probe: still yours, fail loudly later
                fn = mine_fn
                _notices.append(f"mine.{name} raised {type(exc).__name__} on a probe call: check it")
    _cache[name] = fn
    return fn


def using_mine(name: str) -> bool:
    return getattr(get(name), "__module__", "") == "pss_mine"


def notices() -> list[str]:
    out = list(dict.fromkeys(_notices))
    _notices.clear()
    return out
