"""Your mine.py functions where implemented, the references elsewhere.

Every command (`python -m acmeqa ...`, the service, the evaluation) calls the three milestone
functions through Hooks. A mine.py function that still raises NotImplementedError falls back
to the reference, once per process with a note on stderr, so the system always runs and you
see the effect of your code on the evaluation the moment it works. `--reference` (or
Settings(reference=True)) forces the references.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from . import citations, context, router
from .config import PROJECT

_WARNED: set[str] = set()


@dataclass
class Hooks:
    pack_context: Callable
    resolve_citations: Callable
    route_question: Callable
    using: dict


REFS = {"pack_context": context.pack_context, "resolve_citations": citations.resolve_citations,
        "route_question": router.route_question}


def pick_hooks(reference: bool = False) -> Hooks:
    if reference:
        return Hooks(**REFS, using={k: "reference" for k in REFS})
    if str(PROJECT) not in sys.path:
        sys.path.insert(0, str(PROJECT))
    try:
        import mine
    except ImportError:
        return Hooks(**REFS, using={k: "reference (no mine.py)" for k in REFS})
    using: dict[str, str] = {}

    def guarded(name: str) -> Callable:
        fn, ref = getattr(mine, name, None), REFS[name]
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

    return Hooks(pack_context=guarded("pack_context"), resolve_citations=guarded("resolve_citations"),
                 route_question=guarded("route_question"), using=using)
