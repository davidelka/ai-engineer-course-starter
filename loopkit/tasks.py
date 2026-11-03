"""Load tasks from a folder. Each task is a directory with task.json:

    tasks/<id>/task.json          id, title, spec, module, smoke, smoke_imports, impossible
    tasks/<id>/starter/<module>   the buggy starting point the generator sees
    tasks/<id>/tests/             visible tests (the generator sees them)
    tasks/<id>/hidden/            hidden checks: property-based tests, edge cases
    tasks/<id>/reference/<module> a correct solution (never shown to the generator)
    tasks/<id>/scripted/plan.json steps for the offline scripted generators
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from .types import Task


def load_task(path: Path) -> Task:
    meta = json.loads((path / "task.json").read_text(encoding="utf-8"))
    spec = meta["spec"]
    if isinstance(spec, list):  # long specs are stored as a list of lines
        spec = "\n".join(spec)
    return Task(
        id=meta["id"], title=meta["title"], spec=spec, root=path,
        module=meta.get("module", "solution.py"), smoke=meta.get("smoke", ""),
        smoke_imports=meta.get("smoke_imports", ""), impossible=bool(meta.get("impossible", False)),
    )


def load_tasks(root: Path, names: Optional[Iterable[str]] = None, include_impossible: bool = False) -> list[Task]:
    """All tasks under root (sorted), or the named ones. Impossible tasks only when named or asked for."""
    tasks = [load_task(p) for p in sorted(root.iterdir()) if (p / "task.json").exists()]
    wanted = [n for n in (names or []) if n and n != "all"]
    if wanted:
        by_id = {t.id: t for t in tasks}
        missing = [n for n in wanted if n not in by_id]
        if missing:
            raise SystemExit(f"unknown task(s): {', '.join(missing)}; have: {', '.join(by_id)}")
        return [by_id[n] for n in wanted]
    return [t for t in tasks if include_impossible or not t.impossible]
