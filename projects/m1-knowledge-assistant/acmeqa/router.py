"""Routing: is this a question for the documents, or for the database?

"How many open P1 tickets do we have?" has no answer in any document: it is a COUNT over the
tickets table, and the honest answer comes from SQL with provenance (lesson 8). "How many
vacation days can I carry over?" also starts with "how many", and its answer is a sentence in
a policy. A router decides which path a question takes, before any money is spent.

route_question (milestone 6, mine.py) is a small rule-based router, on purpose:
- it is free, instant and deterministic, so it is testable and explainable ("matched: how many
  + tickets");
- a wrong "data" decision is recoverable: if the SQL planner says the tables cannot answer
  (answerable=false), the assistant FALLS BACK to the documents. A wrong "docs" decision is not
  recoverable (the documents simply do not contain live counts), so the rules lean towards
  "data" whenever a count/aggregate cue meets a table entity.
An LLM classifier (one structured call, ~$0.0001) is the natural upgrade; the evaluation's
router section tells you whether the rules are good enough first.

The data path is datakit (lesson 8): semantic layer for the role -> SQLPlan (structured output)
-> SQL guard -> row policy -> read-only execution -> provenance computed by code -> narration.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

from .config import DATA_QUESTIONS

# ------------------------------------------------------------------ the router (reference)
AGG_CUES = [r"\bhow many\b", r"\bnumber of\b", r"\bcount\b", r"\btotal\b", r"\baverage\b", r"\bbreach rate\b",
            r"\blist (?:the|all)\b", r"\btop \d+\b", r"\bmost\b", r"\bper (?:month|plan|priority|team|office)\b",
            r"כמה", r"מספר ה", r"סך הכל", r"סה\"כ", r"ממוצע", r"רשימת"]
ENTITY_CUES = [r"\btickets?\b", r"\bcustomers?\b", r"\baccess grants?\b", r"\bgrants\b", r"\bemployees\b",
               r"\bheadcount\b", r"\bsystems\b", r"\barr\b", r"\bsla breach", r"\bp[1-4]\b",
               r"קריאות", r"קריאת שירות", r"לקוחות", r"עובדים", r"הרשאות", r"מערכות"]
DOC_CUES = [r"\bpolicy\b", r"\bwhy\b", r"\bshould\b", r"\bmay i\b", r"\bcan i\b", r"\ballowed\b", r"\bentitled\b",
            r"\baccrue\b", r"\ballowance\b", r"\bhow do i\b", r"\bprocedure\b", r"\bdeadline\b",
            r"מדיניות", r"למה", r"מותר", r"זכאי", r"איך", r"נוהל"]


@dataclass
class Route:
    kind: str                       # "docs" | "data"
    reason: str
    matched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "reason": self.reason, "matched": self.matched}


def _found(patterns: list[str], text: str) -> list[str]:
    out = []
    for p in patterns:
        m = re.search(p, text)
        if m:
            out.append(m.group(0))
    return out


def route_question(question: str) -> Route:
    q = " ".join(question.lower().split())
    doc = _found(DOC_CUES, q)
    if doc:
        return Route("docs", "policy/process wording", doc)
    agg, ent = _found(AGG_CUES, q), _found(ENTITY_CUES, q)
    if agg and ent:
        return Route("data", "aggregate over a table entity", agg + ent)
    return Route("docs", "no aggregate + table entity", agg + ent)


# ------------------------------------------------------------------ the data path
# Document roles (the ACL of lessons 11/24) -> datakit roles (the semantic layer of lesson 8).
# A contractor gets no structured data at all (fail closed).
DATA_ROLE: dict[str, Optional[str]] = {
    "employee": "analyst", "engineering": "analyst", "security": "analyst",
    "support": "support_lead", "finance": "finance", "hr": "people_ops", "contractor": None,
}


@dataclass
class DataResult:
    status: str                     # ok | not_answerable | rejected | error | forbidden
    answer: str = ""
    data_role: Optional[str] = None
    sql: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def fallback(self) -> bool:
        """The planner said the tables cannot answer: try the documents instead."""
        return self.status == "not_answerable"

    def to_dict(self, max_rows: int = 20) -> dict:
        return {"status": self.status, "answer": self.answer, "data_role": self.data_role, "sql": self.sql,
                "columns": self.columns, "rows": self.rows[:max_rows], "row_count": len(self.rows),
                "provenance": self.provenance, "warnings": self.warnings, "assumptions": self.assumptions,
                "errors": self.errors, "cost_usd": self.cost_usd}


@lru_cache(maxsize=1)
def data_questions() -> tuple[dict, ...]:
    return tuple(json.loads(x) for x in DATA_QUESTIONS.read_text(encoding="utf-8").splitlines() if x.strip())


def offline_data_llm():
    """datakit's replay LLM over the recorded plans in data/data_questions.jsonl. A question that
    is not recorded gets answerable=false, so the assistant falls back to the documents."""
    from datakit.text2sql import replay_llm
    return replay_llm({d["question"].strip(): d for d in data_questions()})


class DataAnswerer:
    def __init__(self, llm: Any):
        self.llm = llm

    def answer(self, question: str, role: str) -> DataResult:
        from datakit.text2sql import Settings as DKSettings
        from datakit.text2sql import answer_question
        data_role = DATA_ROLE.get(role)
        if data_role is None:
            return DataResult("forbidden", "This role has no access to the company's structured data.")
        try:
            ans = answer_question(self.llm, question, DKSettings(role=data_role))
        except Exception as exc:  # noqa: BLE001  (never take the whole request down)
            return DataResult("error", f"The data query failed: {type(exc).__name__}", data_role, errors=[str(exc)])
        prov = ans.provenance.chips() if ans.provenance else []
        return DataResult(status=ans.status, answer=ans.answer, data_role=data_role, sql=ans.sql_executed,
                          columns=list(ans.columns), rows=[list(r) for r in ans.rows], provenance=prov,
                          warnings=list(ans.warnings), assumptions=list((ans.plan or {}).get("assumptions") or []),
                          errors=list(ans.errors), cost_usd=ans.cost_usd, input_tokens=ans.input_tokens,
                          output_tokens=ans.output_tokens)
