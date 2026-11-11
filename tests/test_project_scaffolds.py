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
    for p in (str(ROOT), str(proj)):          # front of the path: other projects also have a mine.py
        while p in sys.path:
            sys.path.remove(p)
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
    _all_todo(hooks, importlib.import_module("mine"))


def _all_todo(hooks, mine):
    for name, milestone in hooks.MILESTONES.items():
        params = inspect.signature(getattr(mine, name)).parameters.values()
        args = [None for p in params if p.default is p.empty and p.kind == p.POSITIONAL_OR_KEYWORD]
        kwargs = {p.name: None for p in params if p.default is p.empty and p.kind == p.KEYWORD_ONLY}
        with pytest.raises(hooks.MilestoneTodo, match=f"milestone {milestone}: mine.{name}"):
            hooks.call(name, *args, **kwargs)


def test_m2_scaffold():
    hooks = _project("m2-personal-search", "pss")
    if hooks.has_reference():
        pytest.skip("solutions branch: the reference implementations are here")
    from pss.config import SAMPLE
    from pss.extract import extract
    from pss.scan import FileEntry
    path = SAMPLE / "home" / "lease-2026.pdf"
    entry = FileEntry(id="home/lease-2026.pdf", path=path, root=SAMPLE, size=path.stat().st_size,
                      mtime=path.stat().st_mtime, ext=".pdf")
    ex = extract(entry, ocr="off")                            # reading files is ready-made
    assert ex.pages >= 2 and any(u.page == 2 for u in ex.units)
    _all_todo(hooks, hooks.load_mine())


def test_f1_scaffold():
    hooks = _project("f1-company-brain", "cbrain")
    if hooks.has_reference():
        pytest.skip("solutions branch: the reference implementations are here")
    from cbrain.auth import load_users
    from cbrain.config import DATA
    assert len(load_users(DATA / "users.json")) >= 3          # identity and keys are ready-made
    _all_todo(hooks, hooks.load_mine())


def test_f2_scaffold():
    hooks = _project("f2-hebrew-tutor", "hebtutor")
    if hooks.has_reference():
        pytest.skip("solutions branch: the reference implementations are here")
    from hebtutor.content import Content
    assert len(Content().scenarios) >= 5                      # the content corpus is ready-made
    _all_todo(hooks, hooks.load_mine())


def test_f3_scaffold():
    hooks = _project("f3-job-agent", "jobagent")
    if hooks.has_reference():
        pytest.skip("solutions branch: the reference implementations are here")
    from jobagent.sources import WhatsAppExportSource
    assert len(WhatsAppExportSource(ROOT / "projects" / "f3-job-agent" / "data" / "whatsapp").fetch()) == 64  # sources are ready-made
    _all_todo(hooks, hooks.load_mine())
