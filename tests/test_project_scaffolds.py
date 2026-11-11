"""What the projects give you on `main`, before any of your code: the scaffolding runs, and every
milestone function you have not written yet fails with a message that names the milestone.

On the `solutions` branch the reference implementations exist and these checks are skipped
(the full project tests in test_m1_*.py ... test_f3_*.py run there instead)."""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _project(name: str, pkg: str):
    proj = ROOT / "projects" / name
    for p in (str(ROOT), str(proj)):
        if p not in sys.path:
            sys.path.insert(0, p)
    for m in [m for m in sys.modules if m == "mine" or m == pkg or m.startswith(pkg + ".")]:
        del sys.modules[m]
    return importlib.import_module(f"{pkg}.hooks")


def test_m1_scaffold(tmp_path):
    hooks = _project("m1-knowledge-assistant", "acmeqa")
    if hooks.has_reference():
        pytest.skip("solutions branch: the reference implementations are here")
    from acmeqa.config import Settings
    from acmeqa.ingest import IngestJob
    job = IngestJob(Settings(index_dir=tmp_path / "idx"))
    rep = job.run()
    assert rep.chunks_added == 404 and not rep.errors        # ingestion is ready-made
    _all_todo(hooks)


def _all_todo(hooks):
    mine = importlib.import_module("mine")
    for name, milestone in hooks.MILESTONES.items():
        params = inspect.signature(getattr(mine, name)).parameters.values()
        args = [None for p in params if p.default is p.empty and p.kind == p.POSITIONAL_OR_KEYWORD]
        with pytest.raises(hooks.MilestoneTodo, match=f"milestone {milestone}: mine.{name}"):
            hooks.call(name, *args)
