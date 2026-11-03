"""Your mine.py functions where implemented, the references elsewhere.

mine.py is loaded by path under the module name "f2_mine" (not "mine"), so it never collides
with the mine.py of a lab or of project F3 when several are imported in one process.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import learner, safety, speaking, validate

PROJECT = Path(__file__).resolve().parent.parent
_WARNED: set[str] = set()
NAMES = {"validate_assessment": validate.validate_assessment, "sm2_update": learner.sm2_update,
         "update_level": learner.update_level, "redact_for_log": safety.redact_for_log,
         "word_feedback": speaking.word_feedback}


@dataclass
class Hooks:
    validate_assessment: Callable = validate.validate_assessment
    sm2_update: Callable = learner.sm2_update
    update_level: Callable = learner.update_level
    redact_for_log: Callable = safety.redact_for_log
    word_feedback: Callable = speaking.word_feedback


def load_mine():
    if "f2_mine" in sys.modules:
        return sys.modules["f2_mine"]
    spec = importlib.util.spec_from_file_location("f2_mine", PROJECT / "mine.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["f2_mine"] = mod
    spec.loader.exec_module(mod)
    return mod


def pick_hooks(reference: bool = False, *, quiet: bool = False) -> Hooks:
    if reference:
        return Hooks()
    mine = load_mine()

    def guarded(name: str) -> Callable:
        fn, ref = getattr(mine, name), NAMES[name]

        def call(*a, **kw):
            try:
                return fn(*a, **kw)
            except NotImplementedError:
                if name not in _WARNED and not quiet:
                    _WARNED.add(name)
                    print(f"  (mine.{name} is still a TODO: using the reference)", file=sys.stderr)
                return ref(*a, **kw)
        return call

    return Hooks(**{n: guarded(n) for n in NAMES})
