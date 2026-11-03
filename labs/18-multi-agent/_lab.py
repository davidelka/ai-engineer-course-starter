"""Shared bits for the lesson 18 scripts: paths, tasks, models, and the --mine switch."""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]

from llmkit import load_dotenv  # noqa: E402

load_dotenv(str(ROOT / ".env"))
LIVE_MODEL = "anthropic:claude-haiku-5-5"
RESULTS = LAB / "results"
TASKS = LAB / "data" / "tasks.jsonl"
RESEARCH = LAB / "data" / "research.jsonl"
CRITIC_CASE = LAB / "data" / "critic_case.json"


def tasks(ids: str = "") -> list[dict]:
    from agentkit import load_tasks
    ts = load_tasks(TASKS)
    if ids:
        want = [x.strip() for x in ids.split(",") if x.strip()]
        ts = [t for t in ts if t["id"] in want or any(w.endswith("*") and t["id"].startswith(w[:-1]) for w in want)]
    return ts


def task_text(task_or_id: str) -> tuple[str, str, dict | None]:
    for t in tasks():
        if t["id"] == task_or_id:
            return t["id"], t["task"], t["gold"]
    return "", task_or_id, None


def is_live(model: str) -> bool:
    return model != "fake"


def mine_or_ref(use_mine: bool):
    """(decide_route, make_handoff_brief, aggregate_runs): yours from mine.py, or multikit's reference."""
    if use_mine:
        import mine
        return mine.decide_route, mine.make_handoff_brief, mine.aggregate_runs
    from multikit import aggregate_runs, decide_route, make_handoff_brief
    return decide_route, make_handoff_brief, aggregate_runs


def money(x: float) -> str:
    return f"${x:.5f}"
