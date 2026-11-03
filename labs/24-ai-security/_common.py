"""Shared helpers for the lesson 24 scripts: path setup, model and layer construction."""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
REPO = LAB.parents[1]
for p in (str(REPO), str(LAB)):
    if p not in sys.path:
        sys.path.insert(0, p)

RESULTS = LAB / "results"
DEFAULT_LIVE = "anthropic:claude-haiku-5-5"


def make_model(spec: str):
    """'obedient' -> the offline SIMULATED model; anything else -> llmkit spec (live or mock:)."""
    from guardkit import LLMKitModel, ObedientModel

    if spec in ("obedient", "sim", "offline"):
        return ObedientModel()
    return LLMKitModel(spec)


def mine_hooks(use_mine: bool) -> dict:
    """Plug the student's validator and ACL from mine.py into build_layers."""
    if not use_mine:
        return {}
    import mine

    return {"check": mine.validate_output, "allows": mine.acl_allows}


def classifier_llm(spec: str):
    from llmkit import LLM, load_dotenv

    load_dotenv(str(REPO / ".env"))
    return LLM(spec)
