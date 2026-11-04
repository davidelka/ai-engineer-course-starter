"""Every image stage must contain the repo code its own code actually imports.

None of the course's Docker images could be built in the sandbox where the course was written
(Docker Hub was blocked), and lesson 27's mockllm stage shipped without llmkit, which
mockllm/vision.py imports at module level: the container crashed on start and never turned
healthy. This test catches that class of bug without Docker.

For each Dockerfile stage it works out what lands in /app (following FROM <stage> inheritance),
then follows module-level imports, starting from the code the image runs: every module of the
copied application folders (projects' code, a lab's service/), and the __init__/__main__ of every
copied library package. If that walk reaches a repo package the stage does not copy, it fails.
Imports inside functions are lazy and are not followed; files nothing imports are not checked.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL = {p.name for p in ROOT.iterdir() if p.is_dir() and (p / "__init__.py").exists()}
DOCKERFILES = sorted(p for p in ROOT.rglob("Dockerfile*")
                     if p.is_file() and not p.name.endswith(".dockerignore") and ".git" not in p.parts)


def parse_stages(text: str) -> list[dict]:
    """[{name, base, copies: [(src, from_stage)]}] in file order. Handles line continuations."""
    text = re.sub(r"\\\n", " ", text)
    stages: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"FROM\s+(\S+)(?:\s+AS\s+(\S+))?", line, re.I)
        if m:
            stages.append({"name": (m.group(2) or f"#{len(stages)}").lower(), "base": m.group(1).lower(), "copies": []})
            continue
        m = re.match(r"COPY\s+(.*)", line, re.I)
        if m and stages:
            frm, rest = None, []
            for a in m.group(1).split():
                if a.startswith("--from="):
                    frm = a.split("=", 1)[1].lower()
                elif not a.startswith("--"):
                    rest.append(a)
            for src in rest[:-1]:  # the last argument is the destination
                stages[-1]["copies"].append((src, frm))
    return stages


def stage_contents(stages: list[dict], name: str) -> tuple[set[str], list[Path]]:
    """(library packages present, application folders present) for a stage, including its base stages."""
    by_name = {s["name"]: s for s in stages}
    libs: set[str] = set()
    apps: list[Path] = []
    chain, cur = [], name
    while cur in by_name and cur not in chain:
        chain.append(cur)
        cur = by_name[cur]["base"]
    for st_name in reversed(chain):
        for src, frm in by_name[st_name]["copies"]:
            if frm is not None:  # another stage (a venv) or an external image (uv): no repo code
                continue
            rel = src.strip("/")
            if rel.startswith("./"):
                rel = rel[2:]
            top = rel.split("/")[0]
            path = ROOT / rel
            if top in LOCAL and rel.rstrip("/") == top:
                libs.add(top)
            elif path.is_dir() and any(path.rglob("*.py")):
                apps.append(path)
            elif path.is_file() and path.suffix == ".py":
                apps.append(path)
    return libs, apps


def module_imports(py: Path, pkg_dir: Path | None) -> set[str]:
    """Absolute dotted names imported at module level (relative imports resolved against pkg_dir)."""
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                out.add(node.module)
                out.update(f"{node.module}.{a.name}" for a in node.names)
            elif node.level and pkg_dir is not None:
                base = pkg_dir
                for _ in range(node.level - 1):
                    base = base.parent
                mod = (node.module or "").replace(".", "/")
                target = base / mod if mod else base
                rel = None
                try:
                    rel = target.relative_to(ROOT)
                except ValueError:
                    pass
                if rel is not None and rel.parts and rel.parts[0] in LOCAL:
                    dotted = ".".join(rel.parts)
                    out.add(dotted)
                    out.update(f"{dotted}.{a.name}" for a in node.names)
    return out


def resolve(dotted: str) -> Path | None:
    """A repo-library module name -> its file (module.py or package/__init__.py)."""
    p = ROOT.joinpath(*dotted.split("."))
    if p.with_suffix(".py").is_file():
        return p.with_suffix(".py")
    if (p / "__init__.py").is_file():
        return p / "__init__.py"
    return None


def missing_for_stage(stages: list[dict], name: str) -> list[str]:
    libs, apps = stage_contents(stages, name)
    roots: list[Path] = []
    for a in apps:
        roots.extend([a] if a.is_file() else sorted(a.rglob("*.py")))
    for lib in libs:
        for f in ("__init__.py", "__main__.py"):
            if (ROOT / lib / f).is_file():
                roots.append(ROOT / lib / f)
    seen: set[Path] = set()
    todo = list(roots)
    problems: set[str] = set()
    while todo:
        py = todo.pop()
        if py in seen:
            continue
        seen.add(py)
        in_lib = py.is_relative_to(ROOT) and py.relative_to(ROOT).parts[0] in LOCAL
        for dotted in module_imports(py, py.parent if in_lib else None):
            top = dotted.split(".")[0]
            if top not in LOCAL:
                continue
            if top not in libs:
                where = py.relative_to(ROOT)
                problems.add(f"stage '{name}': {where} imports {top}, which the stage does not copy")
                continue
            # importing a.b.c also runs a/__init__ and a/b/__init__
            parts = dotted.split(".")
            for i in range(1, len(parts) + 1):
                f = resolve(".".join(parts[:i]))
                if f is not None and f not in seen:
                    todo.append(f)
    return sorted(problems)


@pytest.mark.parametrize("dockerfile", DOCKERFILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_each_stage_has_the_code_its_code_imports(dockerfile: Path):
    stages = parse_stages(dockerfile.read_text(encoding="utf-8"))
    problems = [p for st in stages for p in missing_for_stage(stages, st["name"])]
    assert not problems, "\n".join(problems)


def test_the_check_catches_the_original_lesson_27_bug():
    """The exact stage that shipped broken: mockllm without llmkit."""
    broken = """FROM python:3.12-slim AS runtime
WORKDIR /app
FROM runtime AS mockllm
COPY mockllm/ /app/mockllm/
"""
    problems = missing_for_stage(parse_stages(broken), "mockllm")
    assert any("imports llmkit" in p for p in problems), problems
