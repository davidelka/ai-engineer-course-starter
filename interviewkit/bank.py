"""The interview question bank: loading and validation (lesson 28)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = ROOT / "labs" / "28-interview-prep" / "data" / "question_bank.jsonl"

# id -> Hebrew name. The order is the order of the lesson.
CATEGORIES: dict[str, str] = {
    "fundamentals": "יסודות: טוקנים, דגימה וחלון הקשר",
    "structured": "Structured outputs ו-tool calling",
    "rag": "RAG: chunking, retrieval ו-reranking",
    "embeddings": "Embeddings וחיפוש וקטורי",
    "agents": "סוכנים, כלים ו-workflows",
    "evals": "Evals ו-LLM-as-judge",
    "observability": "Observability ודיבוג",
    "security": "אבטחה ו-prompt injection",
    "cost_latency": "עלות, caching ו-latency",
    "adaptation": "Prompting, RAG או fine-tuning",
    "system_design": "LLM system design",
    "behavioral": "ראיון התנהגותי והסבר החלטות",
}
LEVELS = ("junior", "mid", "senior")
REQUIRED = ("id", "category", "level", "q", "answer", "rubric")


def load_bank(path: Path | str = BANK_PATH) -> list[dict[str, Any]]:
    out = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{n}: {exc}") from None
    return out


def validate_question(q: dict[str, Any]) -> list[str]:
    """Return a list of problems (empty = valid)."""
    probs = [f"missing {k}" for k in REQUIRED if not q.get(k)]
    if probs:
        return probs
    if q["category"] not in CATEGORIES:
        probs.append(f"unknown category {q['category']!r}")
    if q["level"] not in LEVELS:
        probs.append(f"unknown level {q['level']!r}")
    ids = [p.get("id") for p in q["rubric"]]
    if len(set(ids)) != len(ids) or not all(ids):
        probs.append("rubric ids must be unique and non-empty")
    for p in q["rubric"]:
        if not p.get("point") or not p.get("concepts"):
            probs.append(f"rubric {p.get('id')}: needs point and concepts")
        if p.get("weight", 1) <= 0:
            probs.append(f"rubric {p.get('id')}: weight must be > 0")
    for k in ("follow_ups", "red_flags"):
        if k in q and not isinstance(q[k], list):
            probs.append(f"{k} must be a list")
    return probs


def by_id(bank: list[dict]) -> dict[str, dict]:
    return {q["id"]: q for q in bank}
