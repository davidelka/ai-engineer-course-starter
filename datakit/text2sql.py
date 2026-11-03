"""Text-to-SQL with guardrails and provenance (lesson 8).

    question
      -> semantic layer rendered for the user's role (only what they may use)
      -> model writes a SQLPlan (structured output: assumptions, tables_used, answerable, sql)
      -> guard: parse, allow-lists, sensitive columns, LIMIT   (rejected? reason goes back to
         the model for one repair turn)
      -> row policy rewrite (manager sees only their team)
      -> read-only execution with timeout and row cap
      -> provenance computed by code: tables, source systems, extraction time, row ids,
         freshness warnings
      -> a short natural-language answer, written from the rows (PII masked before the
         rows are sent to the model)

    from datakit.text2sql import answer_question, Settings
    ans = answer_question(llm, "How many open P1 tickets are there?", Settings(role="analyst"))
    print(format_answer(ans))

Offline: replay_llm(fixtures) is a real llmkit LLM whose HTTP transport answers from
recorded replies, so the whole request path (native schema included) runs for free.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict, Field

from llmkit import LLM, ChatRequest, Message
from llmkit.structured import StructuredError, complete_structured

from . import db as dbmod
from .freshness import default_now, max_age_from_layer, stale_warnings
from .guard import GuardResult, guard_sql
from .provenance import Provenance, build_provenance
from .rls import apply_row_policy
from .semantic import Layer, load_layer, policy_from_layer, render_context


class SQLPlan(BaseModel):
    """What the model returns. Reasoning-ish fields first: the model writes in this order."""

    model_config = ConfigDict(extra="forbid")
    assumptions: list[str] = Field(description="Short assumptions about the question, e.g. which "
                                   "metric definition or date range you used. Empty list if none.")
    tables_used: list[str] = Field(description="Tables the query reads")
    answerable: bool = Field(description="false when these tables cannot answer the question "
                             "(the answer is in documents, or the data does not exist)")
    sql: Optional[str] = Field(description="Exactly one SQLite SELECT statement, or null when not answerable")
    clarification: Optional[str] = Field(description="When not answerable: what is missing, one sentence. "
                                         "Otherwise null.")


SYSTEM = """You translate business questions about Acme into ONE SQLite SELECT query.
Use only the tables, columns, join paths, business terms and metric definitions below.
Rules:
- Use metric and term definitions exactly as written (they are the company's official ones).
- Use enum values exactly as listed (case matters).
- List columns explicitly; do not use SELECT *.
- Questions about "top", "most", "highest": ORDER BY and LIMIT.
- Rates: ROUND(..., 4) as a fraction (0.1552), not a percent.
- Give result columns short snake_case aliases.
- If the tables cannot answer the question (policies, explanations and reasons live in
  documents; some data simply does not exist), set answerable=false, sql=null, and say
  what is missing in clarification.
A guard checks your SQL before it runs. If it rejects the query you will get the reason;
fix exactly that.

{context}"""

REJECTED = ("Your query was rejected and did not run: {reason}\n"
            "Return a corrected JSON object. If the question cannot be answered with the allowed "
            "tables and columns, set answerable=false.")

NARRATE_SYSTEM = """You answer a business question from the result of a SQL query.
Use only the numbers in the result. 1-3 sentences, plain text. If the result is empty, say so.
If a warning says data is stale or truncated, mention it. Do not invent sources: the
application shows provenance separately."""

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


@dataclass
class Settings:
    role: str = "analyst"
    user: dict = field(default_factory=dict)  # row-policy parameters, e.g. {"team": "core-api"}
    db_path: Optional[str] = None
    layer: Optional[Layer] = None
    now: Optional[str] = None
    mode: str = "native"  # structured output mode
    max_repairs: int = 1
    narrate: bool = True
    # injectable pieces, so the lab can plug in mine.py versions
    guard: Callable[..., GuardResult] = guard_sql
    row_policy: Callable[[str, dict, dict], str] = apply_row_policy


@dataclass
class DataAnswer:
    question: str
    role: str
    status: str = "ok"  # ok | not_answerable | rejected | error
    plan: Optional[dict] = None
    sql_model: str = ""
    sql_executed: str = ""
    guard_changes: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    truncated: bool = False
    provenance: Optional[Provenance] = None
    warnings: list[str] = field(default_factory=list)
    answer: str = ""
    attempts: int = 0
    errors: list[str] = field(default_factory=list)  # guard/db errors that triggered repairs
    raw_replies: list[str] = field(default_factory=list)  # model replies, for --record
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


def redact_for_llm(columns: list[str], rows: list[tuple]) -> list[tuple]:
    """Data minimization: the user may see PII on screen, the model does not need it."""
    out = []
    for r in rows:
        out.append(tuple(EMAIL.sub("<email>", v) if isinstance(v, str) else v for v in r))
    return out


def build_system(layer: Layer, role: str) -> str:
    return SYSTEM.format(context=render_context(layer, role=role))


def _rows_text(columns: list[str], rows: list[tuple], limit: int = 20) -> str:
    lines = [" | ".join(columns)]
    for r in rows[:limit]:
        lines.append(" | ".join("NULL" if v is None else str(v) for v in r))
    if len(rows) > limit:
        lines.append(f"... {len(rows) - limit} more rows")
    return "\n".join(lines)


def answer_question(llm: LLM, question: str, s: Settings, con: Optional[sqlite3.Connection] = None) -> DataAnswer:
    layer = s.layer or load_layer()
    policy = policy_from_layer(layer)
    role_def = layer.role(s.role)
    own_con = con is None
    con = con or dbmod.connect_ro(s.db_path)
    ans = DataAnswer(question=question, role=s.role)
    system = build_system(layer, s.role)
    who = ", ".join([f"role={s.role}"] + [f"{k}={v}" for k, v in s.user.items()])
    messages = [Message("user", f"Question: {question}\nUser: {who}")]
    try:
        result = None
        for attempt in range(1 + s.max_repairs):
            req = ChatRequest(messages=list(messages), system=system, max_tokens=900)
            try:
                res = complete_structured(llm, req, SQLPlan, mode=s.mode, max_repairs=1)
            except StructuredError as e:
                ans.status, ans.errors = "error", ans.errors + [f"structured output failed: {e.stage}"]
                if e.result:
                    ans.cost_usd += e.result.cost_usd
                return ans
            ans.attempts += 1
            ans.cost_usd += res.cost_usd
            ans.input_tokens += res.input_tokens
            ans.output_tokens += res.output_tokens
            ans.raw_replies.append(res.text)
            plan: SQLPlan = res.value
            ans.plan = plan.model_dump()
            if not plan.answerable or not plan.sql:
                ans.status = "not_answerable"
                ans.answer = plan.clarification or "The data cannot answer this question."
                return ans
            ans.sql_model = plan.sql
            g = s.guard(plan.sql, policy, s.role)
            if not g.ok:
                ans.errors.append(f"guard: {g.reason}")
                messages += [Message("assistant", res.text), Message("user", REJECTED.format(reason=g.reason))]
                ans.status = "rejected"
                continue
            sql = g.sql
            if role_def.row_policy:
                sql = s.row_policy(sql, role_def.row_policy, s.user)
            try:
                result = dbmod.run_query(con, sql, max_rows=layer.limits.row_limit,
                                         timeout_ms=layer.limits.timeout_ms)
            except (sqlite3.Error, dbmod.QueryTimeout) as e:
                ans.errors.append(f"database: {e}")
                messages += [Message("assistant", res.text),
                             Message("user", REJECTED.format(reason=f"database error: {e}"))]
                ans.status = "error"
                continue
            ans.status = "ok"
            ans.sql_executed, ans.guard_changes = sql, g.changes
            ans.columns, ans.rows, ans.truncated = result.columns, result.rows, result.truncated
            pks = {t: tab.primary_key for t, tab in layer.tables.items()}
            ans.provenance = build_provenance(con, sql, g.tables, pks, s.now or default_now(layer),
                                              max_age_from_layer(layer))
            ans.warnings = stale_warnings(ans.provenance.freshness)
            if result.truncated:
                ans.warnings.append(f"result truncated to {layer.limits.row_limit} rows")
            break
        if ans.status != "ok":
            ans.answer = "I could not produce a safe query for this question. Last problem: " + (ans.errors[-1] if ans.errors else "unknown")
            return ans
        ans.answer = narrate(llm, question, ans) if s.narrate else _plain_answer(ans)
        return ans
    finally:
        if own_con:
            con.close()


def _plain_answer(ans: DataAnswer) -> str:
    if not ans.rows:
        return "The query returned no rows."
    if len(ans.rows) == 1 and len(ans.columns) <= 3:
        return ", ".join(f"{c} = {v}" for c, v in zip(ans.columns, ans.rows[0]))
    return f"{len(ans.rows)} rows (see the table)."


def narrate(llm: LLM, question: str, ans: DataAnswer) -> str:
    rows = redact_for_llm(ans.columns, ans.rows)
    body = (f"Question: {question}\n\nSQL that ran:\n{ans.sql_executed}\n\nResult:\n{_rows_text(ans.columns, rows)}\n\n"
            f"Warnings: {'; '.join(ans.warnings) if ans.warnings else 'none'}")
    r = llm.complete(ChatRequest(messages=[Message("user", body)], system=NARRATE_SYSTEM, max_tokens=300))
    ans.cost_usd += r.cost_usd or 0.0
    ans.input_tokens += r.usage.input_tokens
    ans.output_tokens += r.usage.output_tokens
    ans.raw_replies.append(r.text)
    return r.text.strip()


def format_answer(ans: DataAnswer, show_rows: int = 8) -> str:
    out = [f"Q: {ans.question}   [role: {ans.role}]"]
    if ans.plan and ans.plan.get("assumptions"):
        out.append("assumptions: " + "; ".join(ans.plan["assumptions"]))
    for e in ans.errors:
        out.append(f"  ! {e}")
    if ans.sql_executed:
        out.append("SQL executed:\n  " + ans.sql_executed)
        if ans.guard_changes:
            out.append("guard changed: " + ", ".join(ans.guard_changes))
    if ans.columns:
        out.append("result: " + " | ".join(ans.columns))
        for r in ans.rows[:show_rows]:
            out.append("  " + " | ".join("NULL" if v is None else str(v) for v in r))
        if len(ans.rows) > show_rows:
            out.append(f"  ... {len(ans.rows) - show_rows} more")
    out.append(f"A ({ans.status}): {ans.answer}")
    if ans.provenance:
        out.append("sources:")
        out += [f"  [{c}]" for c in ans.provenance.chips()]
    for w in ans.warnings:
        out.append(f"  WARNING {w}")
    out.append(f"attempts {ans.attempts} · tokens {ans.input_tokens}+{ans.output_tokens} · ${ans.cost_usd:.5f}")
    return "\n".join(out)


# ------------------------------------------------------------------ offline replay
def load_fixtures(path: Path) -> dict[str, dict]:
    """JSONL: {"question", "plans": [<reply text>, ...], "answer": <text>}"""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out[d["question"].strip()] = d
    return out


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict))


def replay_llm(fixtures: dict[str, dict], model: str = "claude-haiku-5-5") -> LLM:
    """An llmkit LLM whose HTTP layer answers from recorded replies (Anthropic format).

    Plan calls (with a schema) return plans[k], where k = how many assistant turns are
    already in the conversation (so a repair turn gets the second recorded plan).
    Narration calls return `answer`. Usage is estimated (chars/4), so the cost shown is
    what Haiku would roughly have cost, not a real bill."""
    import httpx

    from ctxkit.tokens import count_tokens

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        msgs = body.get("messages", [])
        first = _text_of(msgs[0]["content"]) if msgs else ""
        m = re.search(r"Question:\s*(.+)", first)
        q = m.group(1).strip() if m else ""
        fx = fixtures.get(q)
        schema_call = bool((body.get("output_config") or {}).get("format"))
        if schema_call:
            k = sum(1 for x in msgs if x["role"] == "assistant")
            if fx and fx.get("plans"):
                text = fx["plans"][min(k, len(fx["plans"]) - 1)]
            else:
                text = json.dumps({"assumptions": [], "tables_used": [], "answerable": False, "sql": None,
                                   "clarification": "replay mode: no recorded reply for this question"})
        else:
            text = (fx or {}).get("answer") or "(replay) no recorded narration for this question."
        prompt = json.dumps(body)
        out = {"id": "msg_replay", "type": "message", "role": "assistant", "model": body.get("model"),
               "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
               "usage": {"input_tokens": count_tokens(prompt), "output_tokens": count_tokens(text)}}
        return httpx.Response(200, json=out, headers={"request-id": "req_replay"})

    return LLM(f"anthropic:{model}", api_key="replay", base_url="http://replay.invalid",
               http=httpx.Client(transport=httpx.MockTransport(handler)))
