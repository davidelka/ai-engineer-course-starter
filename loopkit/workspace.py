"""Workspaces: a temporary folder per verification, and a subprocess runner with a timeout.

Model-written code runs here. A subprocess with a timeout protects the loop from
infinite loops and crashes, NOT from malicious code: for untrusted code use a
container or a sandbox service (lesson 27).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

PYTEST_INI = "[pytest]\naddopts = -p no:cacheprovider\n"


def apply_files(base: dict[str, str], changes: dict[str, Optional[str]]) -> dict[str, str]:
    """base + changes; a change of None deletes the file."""
    out = dict(base)
    for path, content in changes.items():
        if content is None:
            out.pop(path, None)
        else:
            out[path] = content
    return out


def write_files(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = root / rel
        if root.resolve() not in p.resolve().parents and p.resolve() != root.resolve():
            raise ValueError(f"path escapes the workspace: {rel!r}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


@contextmanager
def room(files: dict[str, str], *, pytest_ini: bool = True) -> Iterator[Path]:
    """A fresh temporary folder holding exactly `files` (plus a pytest.ini that pins rootdir)."""
    with tempfile.TemporaryDirectory(prefix="loopkit-") as d:
        root = Path(d)
        if pytest_ini and "pytest.ini" not in files:
            (root / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8")
        write_files(root, files)
        yield root


@dataclass
class CmdResult:
    code: int
    out: str
    timed_out: bool = False


def run_cmd(args: list[str], cwd: Path, timeout: float = 60.0) -> CmdResult:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(cwd),
           "PYTHONHASHSEED": "0", "NO_COLOR": "1"}
    try:
        p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return CmdResult(p.returncode, (p.stdout or "") + (p.stderr or ""))
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return CmdResult(124, out + f"\n[loopkit] timed out after {timeout:.0f}s", timed_out=True)


def python() -> str:
    return sys.executable
