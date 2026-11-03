"""A mock AI-engineering interviewer on top of llmkit (lesson 28).

Two LLM roles, kept apart on purpose:

- The *interviewer* sees the question, the hidden reference answer and rubric,
  and the conversation so far. Each turn it returns a structured decision:
  ask one follow-up that probes a missing rubric point, or finish.
- The *grader* sees only the final transcript and the rubric. It judges every
  rubric point as covered / not covered (binary, with a quote as evidence).
  The score is computed in code from those verdicts and the weights, not
  invented by the model: a judge is better at yes/no questions than at "7/10".

Everything goes through llmkit.structured, so the offline path is the mock
server (python -m mockllm, or start_in_thread in tests).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

from pydantic import BaseModel, Field

from llmkit import LLM
from llmkit.structured import complete_structured
from llmkit.types import ChatRequest, Message

from .rubric import score_answer

LANGS = {"he": "Hebrew (keep technical terms in English, as Israeli interviewers do)", "en": "English"}


class InterviewerTurn(BaseModel):
    reasoning: str = Field(description="One short sentence for the log only: which rubric point is still "
                                       "missing or weak, or why the answer is complete.")
    action: Literal["follow_up", "finish"] = Field(description="follow_up = ask one more question; "
                                                               "finish = end this question")
    message: str = Field(description="What you say to the candidate. For finish: a one-line neutral close.")


class CriterionVerdict(BaseModel):
    point_id: str = Field(description="The rubric point id, exactly as given (r1, r2, ...)")
    evidence: Optional[str] = Field(None, description="A short quote from the candidate that covers the "
                                                      "point, or null if there is none")
    covered: bool = Field(description="true only if the quote shows the point was really covered")


class Grade(BaseModel):
    criteria: list[CriterionVerdict]
    red_flags: list[str] = Field(description="Concrete red flags in the candidate's answers (may be empty)")
    structure_note: str = Field(description="One sentence on structure: direct answer first, trade-offs, "
                                            "numbers, measurement")
    feedback: str = Field(description="2-4 sentences in Hebrew: what to add or change next time")


INTERVIEWER_SYSTEM = """You are a senior AI engineer interviewing a candidate for an AI Engineer role at an Israeli tech company.
Speak {lang}. Keep every message under 60 words. Be neutral: do not praise, hint or teach during the interview.

You hold a hidden reference answer and a rubric. Never reveal or quote them.
After each candidate answer, decide:
- follow_up: if an important rubric point is missing or vague, ask ONE short question that probes it
  without giving the answer away (e.g. "How would you measure that?", "What breaks first at 10x traffic?").
  Prefer the follow-ups listed below when they fit.
- finish: if the rubric is covered, or you have already asked {max_followups} follow-ups.

<question>{question}</question>
<reference_answer>{answer}</reference_answer>
<rubric>
{rubric}
</rubric>
<suggested_follow_ups>
{follow_ups}
</suggested_follow_ups>"""

GRADER_SYSTEM = """You grade a candidate's technical interview answer (or design document) against a rubric.
Be strict and literal. For EVERY rubric point return a verdict: covered=true only if you can quote the
candidate's own words that cover it. No quote, no credit. Knowledge the interviewer supplied in a follow-up
does not count, and naming a buzzword without saying what it does or why does not count either.
Red flags to watch for in this question: {red_flags}
Write the feedback in Hebrew, with technical terms in English."""

PROJECT_RUBRIC = [
    {"id": "p1", "point": "הבעיה והמשתמש: למי זה, מה הכאב, ואיך נראית הצלחה", "weight": 1,
     "concepts": [["משתמש", "user"], ["בעיה", "problem", "כאב"], ["הצלחה", "success"]], "need": 2},
    {"id": "p2", "point": "ארכיטקטורה בכמה משפטים: הרכיבים העיקריים והזרימה", "weight": 2,
     "concepts": [["architecture", "ארכיטקטורה"], ["rag", "retrieval", "agent", "workflow", "pipeline"],
                  ["api", "fastapi", "queue", "database", "מסד"]], "need": 2},
    {"id": "p3", "point": "החלטה אחת עם trade-off מפורש וחלופה שנדחתה", "weight": 2,
     "concepts": [["החלטתי", "בחרתי", "decided", "chose"], ["trade off", "tradeoff", "על חשבון", "לעומת",
                                                            "חלופה", "instead of", "במקום"]], "need": 2},
    {"id": "p4", "point": "מדידה: eval, golden set ומספרים אמיתיים (דיוק, latency, עלות)", "weight": 2,
     "concepts": [["eval", "golden set", "מדדתי", "מדידה"], ["%", "אחוז", "p95", "latency", "עלות", "cost"]],
     "need": 2},
    {"id": "p5", "point": "כשל אמיתי: מה נשבר, איך גילית (trace, eval) ומה תיקנת", "weight": 2,
     "concepts": [["נכשל", "נשבר", "באג", "bug", "failure", "כשל"], ["trace", "log", "eval", "גיליתי"],
                  ["תיקנתי", "fixed", "שיניתי"]], "need": 2},
    {"id": "p6", "point": "מה הייתי עושה אחרת או הצעד הבא", "weight": 1,
     "concepts": [["אחרת", "differently", "הצעד הבא", "next step", "הייתי משנה", "בדיעבד"]]},
]


def project_question(project_text: str, title: str = "your project") -> dict:
    return {
        "id": "project", "category": "behavioral", "level": "mid",
        "q": f"ספר לי על {title} בחמש דקות: הבעיה, הארכיטקטורה, החלטה אחת שקיבלת ולמה, ואיך מדדת שזה עובד.",
        "answer": "The candidate's own project write-up (use it to probe decisions and numbers):\n" + project_text,
        "rubric": PROJECT_RUBRIC,
        "follow_ups": ["למה לא בחרת בחלופה הפשוטה יותר?", "איך ידעת שזה עובד? תן מספר.",
                       "מה נשבר ראשון כשהעומס גדל פי 10?", "מה היית עושה אחרת היום?"],
        "red_flags": ["אין מספרים בכלל", "\"השתמשתי ב-X כי זה מה שכולם עושים\"", "לא יודע להסביר כשל אמיתי"],
    }


def _rubric_text(q: dict) -> str:
    return "\n".join(f"{p['id']} (weight {p.get('weight', 1)}): {p['point']}" for p in q["rubric"])


@dataclass
class InterviewResult:
    question_id: str
    transcript: list[tuple[str, str]] = field(default_factory=list)  # (interviewer|candidate, text)
    grade: Optional[Grade] = None
    score: int = 0  # 0-100, from the grader's verdicts and the rubric weights
    covered: list[str] = field(default_factory=list)
    local: dict = field(default_factory=dict)  # the keyword rubric scorer, for comparison
    calls: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0

    def to_dict(self) -> dict:
        return {"question_id": self.question_id, "transcript": self.transcript, "score": self.score,
                "covered": self.covered, "grade": self.grade.model_dump() if self.grade else None,
                "local": self.local, "calls": self.calls, "cost_usd": round(self.cost_usd, 6),
                "latency_s": round(self.latency_s, 2)}


def weighted_score(question: dict, verdicts: list[CriterionVerdict]) -> tuple[int, list[str]]:
    """Weighted share of rubric points the grader marked covered. Unknown ids are ignored."""
    ok = {v.point_id for v in verdicts if v.covered}
    covered = [p["id"] for p in question["rubric"] if p["id"] in ok]
    total = sum(p.get("weight", 1) for p in question["rubric"])
    got = sum(p.get("weight", 1) for p in question["rubric"] if p["id"] in ok)
    return round(100 * got / total), covered


@dataclass
class Graded:
    grade: Grade
    score: int
    covered: list[str]
    calls: int
    cost_usd: float


def grade_answer(llm: LLM, question: dict, material: str, max_tokens: int = 1500) -> Graded:
    """Binary verdict per rubric point (with a quote), score computed in code.

    `material` is what gets graded: a <transcript>...</transcript> or a <design_doc>...</design_doc>.
    """
    r = complete_structured(llm, ChatRequest(
        messages=[Message("user", f"<rubric>\n{_rubric_text(question)}\n</rubric>\n\n{material}")],
        system=GRADER_SYSTEM.format(red_flags="; ".join(question.get("red_flags", [])) or "(none listed)"),
        max_tokens=max_tokens), Grade)
    score, covered = weighted_score(question, r.value.criteria)
    return Graded(r.value, score, covered, r.attempts, r.cost_usd)


def run_interview(llm: LLM, question: dict, answer_fn: Callable[[str], str], *, lang: str = "he",
                  max_followups: int = 2, on_message: Optional[Callable[[str, str], None]] = None,
                  scorer: Callable[[str, dict], dict] = score_answer) -> InterviewResult:
    """Ask the question, up to max_followups follow-ups, then grade.

    answer_fn(interviewer_message) returns the candidate's answer (input(), a file, a test stub).
    on_message(role, text) is called for every line of the transcript, for printing.
    """
    res = InterviewResult(question_id=question["id"])
    t0 = time.perf_counter()
    say = on_message or (lambda role, text: None)

    def add(role: str, text: str) -> None:
        res.transcript.append((role, text))
        say(role, text)

    def account(r) -> None:
        res.calls += r.attempts
        res.cost_usd += r.cost_usd

    system = INTERVIEWER_SYSTEM.format(
        lang=LANGS.get(lang, lang), max_followups=max_followups, question=question["q"],
        answer=question["answer"], rubric=_rubric_text(question),
        follow_ups="\n".join(question.get("follow_ups", [])) or "(none)")

    opening = question["q"]
    if lang != "he":
        r = complete_structured(llm, ChatRequest(
            messages=[Message("user", "[The candidate joined. Ask the interview question now, in your language.]")],
            system=system, max_tokens=400), InterviewerTurn)
        account(r)
        opening = r.value.message
    add("interviewer", opening)

    followups = 0
    while True:
        add("candidate", answer_fn(res.transcript[-1][1]))
        if followups >= max_followups:
            break
        msgs = [Message("user", "[The candidate joined.]")]
        for role, text in res.transcript:
            msgs.append(Message("assistant" if role == "interviewer" else "user", text))
        r = complete_structured(llm, ChatRequest(messages=msgs, system=system, max_tokens=500), InterviewerTurn)
        account(r)
        turn: InterviewerTurn = r.value
        if turn.action == "finish":
            add("interviewer", turn.message)
            break
        followups += 1
        add("interviewer", turn.message)

    transcript_text = "\n\n".join(f"{role.upper()}: {text}" for role, text in res.transcript)
    g = grade_answer(llm, question, f"<transcript>\n{transcript_text}\n</transcript>")
    res.calls += g.calls
    res.cost_usd += g.cost_usd
    res.grade, res.score, res.covered = g.grade, g.score, g.covered
    candidate_text = "\n".join(t for role, t in res.transcript if role == "candidate")
    res.local = scorer(candidate_text, question)
    res.latency_s = time.perf_counter() - t0
    return res
