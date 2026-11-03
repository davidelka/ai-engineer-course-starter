"""Pattern 5: generator + critic (evaluator-optimizer), with a rubric and a round limit.

    draft = writer(task, facts, feedback)          plain LLM call
    code checks  (length, required facts)          deterministic: free and never wrong
    review = critic(draft, rubric)                 structured output: one verdict per criterion
    stop when every criterion passes, or after max_rounds

Two rules make this loop worth its cost. First, check in CODE whatever code can check
(word count, the request id is present) and give the critic only the criteria that need
judgment. Second, the critic must be independent of the writer: a fresh context with the
rubric and the draft, not the writer's conversation (Cognition's review loop works "with
clean context" for the same reason). A critic that always passes is a rubber stamp; one that
always finds something burns rounds until max_rounds. Both are measurable.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, Field

from llmkit.structured import complete_structured
from llmkit.types import ChatRequest, Message

from .attribution import AgentRun, MultiResult, llm_call_records


class CriterionResult(BaseModel):
    id: str = Field(description="The criterion id from the rubric")
    passed: bool
    note: str = Field(description="One short sentence: why it passed or what exactly to fix")


class Review(BaseModel):
    criteria: list[CriterionResult] = Field(description="One entry per rubric criterion, in rubric order")
    passed: bool = Field(description="true only if every criterion passed")
    summary: str = Field(description="One sentence overall")


DEFAULT_RUBRIC = [
    {"id": "facts", "check": "code", "text": "Mentions the request id, the system and the approver."},
    {"id": "length", "check": "code", "text": "At most 80 words."},
    {"id": "no_promise", "check": "llm", "text": "Does not say or imply that access is already granted or active."},
    {"id": "next_step", "check": "llm", "text": "Says who reviews it next, within how many business days, and when the "
                                                "access expires."},
    {"id": "plain_language", "check": "llm", "text": "Explains the approval track in plain words (no bare internal "
                                                     "codes like needs_security without an explanation)."},
]

WRITER_SYSTEM = ("You write short Slack replies from Company Brain to Acme employees about their access requests. "
                 "Use only the facts given. If <feedback> is present, fix exactly the failed criteria and keep "
                 "everything else.")
CRITIC_SYSTEM = ("You review a draft reply against a rubric. Judge each criterion independently and strictly; pass "
                 "it only if the draft clearly meets it. Do not rewrite the draft.")


def code_checks(draft: str, facts: dict, rubric: list[dict], max_words: int = 80) -> list[CriterionResult]:
    clean = re.sub(r"<!--.*?-->", "", draft)
    out = []
    for c in rubric:
        if c.get("check") != "code":
            continue
        if c["id"] == "length":
            n = len(clean.split())
            out.append(CriterionResult(id="length", passed=n <= max_words, note=f"{n} words (max {max_words})"))
        elif c["id"] == "facts":
            need = [str(facts.get(k)) for k in ("request_id", "system", "approver") if facts.get(k)]
            miss = [x for x in need if x.lower() not in clean.lower()]
            out.append(CriterionResult(id="facts", passed=not miss, note="ok" if not miss else f"missing {', '.join(miss)}"))
    return out


@dataclass
class CriticLoop:
    writer_llm: object
    critic_llm: object
    rubric: list[dict] = field(default_factory=lambda: list(DEFAULT_RUBRIC))
    max_rounds: int = 3
    max_words: int = 80

    def run(self, task: str, facts: dict, *, task_id: str = "") -> MultiResult:
        t0 = time.perf_counter()
        runs: list[AgentRun] = []
        rounds: list[dict] = []
        draft, feedback = "", ""
        llm_crit = [c for c in self.rubric if c.get("check") != "code"]
        stop = "max_rounds"
        for k in range(1, self.max_rounds + 1):
            prompt = (f"<task>\n{task}\n</task>\n<facts>\n{json.dumps(facts, ensure_ascii=False)}\n</facts>"
                      + (f"\n<previous_draft>{draft}</previous_draft>\n<feedback>\n{feedback}\n</feedback>" if feedback else ""))
            ts, ts_ms = time.perf_counter(), time.time() * 1000
            r = self.writer_llm.complete(ChatRequest(messages=[Message("user", prompt)], system=WRITER_SYSTEM,
                                                     max_tokens=400))
            draft = r.text
            runs.append(_run("writer", llm_call_records(
                "writer", "worker", input_tokens=r.usage.input_tokens, output_tokens=r.usage.output_tokens,
                cost_usd=r.cost_usd or 0.0, elapsed_s=time.perf_counter() - ts, text=draft, task_id=task_id,
                t0_ms=ts_ms, estimated=bool(getattr(self.writer_llm, "estimated", False)))))
            results = code_checks(draft, facts, self.rubric, self.max_words)
            if llm_crit:
                rub = "\n".join(f"- {c['id']}: {c['text']}" for c in llm_crit)
                clean = re.sub(r"<!--.*?-->", "", draft)
                cprompt = f"<rubric>\n{rub}\n</rubric>\n<facts>\n{json.dumps(facts)}\n</facts>\n<draft>\n{clean}\n</draft>"
                ts, ts_ms = time.perf_counter(), time.time() * 1000
                sr = complete_structured(self.critic_llm, cprompt, Review, system=CRITIC_SYSTEM, max_tokens=600)
                by_id = {c.id: c for c in sr.value.criteria}
                for c in llm_crit:  # a criterion the critic skipped counts as failed
                    results.append(by_id.get(c["id"]) or CriterionResult(id=c["id"], passed=False, note="not reviewed"))
                runs.append(_run("critic", llm_call_records(
                    "critic", "coordinator", input_tokens=sr.input_tokens, output_tokens=sr.output_tokens,
                    cost_usd=sr.cost_usd, elapsed_s=time.perf_counter() - ts, text=sr.value.model_dump_json(),
                    task_id=task_id, t0_ms=ts_ms, estimated=bool(getattr(self.critic_llm, "estimated", False)))))
            failed = [c for c in results if not c.passed]
            rounds.append({"round": k, "draft": re.sub(r"<!--.*?-->", "", draft),
                           "results": [c.model_dump() for c in results], "failed": [c.id for c in failed],
                           "cost_usd": sum(x.cost_usd for x in runs[-(2 if llm_crit else 1):])})
            if not failed:
                stop = "passed"
                break
            feedback = "\n".join(f"{c.id}: FAIL ({c.note})" for c in failed)
        text = re.sub(r"<!--.*?-->", "", draft)
        return MultiResult("critic", text, stop, runs, time.perf_counter() - t0, task_id, {"rounds": rounds})


def _run(name: str, recs: list[dict]) -> AgentRun:
    return AgentRun(name, recs[0]["role"], recs, None, recs[-1]["text"], "final_answer")
