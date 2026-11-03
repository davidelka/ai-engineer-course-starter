"""Shared helpers for the lesson 8 scripts: paths, and picking your functions (mine.py)
or the reference ones (datakit) with --reference."""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
RESULTS = LAB / "results"
GOLDEN = LAB / "golden" / "business_questions.jsonl"
FIXTURES = LAB / "fixtures" / "replay.jsonl"
MY_LAYER = LAB / "semantic" / "my_semantic.yaml"
DEFAULT_MODEL = "anthropic:claude-haiku-5-5"


def pick(name: str, reference: bool):
    """Return (function, source). Falls back to the reference while yours is still a TODO."""
    import datakit.evaluate
    import datakit.freshness
    import datakit.guard
    import datakit.rls

    ref = {
        "guard_sql": datakit.guard.guard_sql,
        "results_match": datakit.evaluate.results_match,
        "apply_row_policy": datakit.rls.apply_row_policy,
        "freshness_report": datakit.freshness.freshness_report,
    }[name]
    if reference:
        return ref, "reference"
    import mine

    fn = getattr(mine, name)
    probe = {
        "guard_sql": lambda f: f("SELECT 1", _probe_policy(), "analyst"),
        "results_match": lambda f: f([(1,)], [(1,)]),
        "apply_row_policy": lambda f: f("SELECT 1", {}, {}),
        "freshness_report": lambda f: f(_probe_con(), [], "2026-11-01T00:00:00Z"),
    }[name]
    try:
        probe(fn)
    except NotImplementedError:
        print(f"(mine.{name} is still a TODO: using the reference implementation)")
        return ref, "reference (yours is a TODO)"
    except Exception:
        pass  # implemented, maybe buggy: let the real call show it
    return fn, "mine.py"


def _probe_policy():
    from datakit.guard import Policy
    return Policy(columns={"t": ["a"]}, roles={"analyst": {"tables": ["t"], "sees": []}})


def _probe_con():
    import sqlite3
    return sqlite3.connect(":memory:")


def make_llm(live: bool, model: str):
    """Live: a real llmkit LLM (needs the key in .env). Offline: replay of fixtures/replay.jsonl."""
    from datakit.text2sql import load_fixtures, replay_llm
    if live:
        from llmkit import LLM, load_dotenv
        load_dotenv(str(ROOT / ".env"))
        return LLM(model), model
    return replay_llm(load_fixtures(FIXTURES)), "replay (fixtures/replay.jsonl)"
