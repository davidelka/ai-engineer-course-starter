"""Pure domain logic of the answer service: no I/O, no clock, no network.

Not everything is a port. A rule like "no salary questions" is the business
itself: it is fast, deterministic and owned by us, so it lives here as a plain
function and is tested directly. Ports are for things that are slow,
non-deterministic, external, or likely to be replaced.
"""

from __future__ import annotations

import re

from .types import Passage, PolicyDecision, PromptVersion

ACME_DOMAIN = "@acme.example"

# Words that carry no meaning for keyword search.
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from get got have how i if in is it its me my of on or our "
    "please should so than that the their them there they this to up us was we what when where which who "
    "will with would you your".split()
)

NO_CONTEXT_TEXT = ("I could not find this in Acme's documents, so I won't guess. "
                   "Try rephrasing, or ask HR or IT directly.")

ANSWER_PROMPT_V1 = PromptVersion(
    name="answer",
    version="1.0.0",
    template=(
        "You are Company Brain, Acme's internal assistant. Answer the employee's question using ONLY "
        "the documents provided. After every fact, cite its source as [doc_id], for example "
        "[vacation_policy.md]. If the documents do not contain the answer, say that you don't know. "
        "Be brief: at most four sentences."
    ),
)


def policy_check(question: str, user_email: str) -> PolicyDecision:
    """Rules that run BEFORE anything leaves the building (retrieval, model call)."""
    if not user_email.lower().strip().endswith(ACME_DOMAIN):
        return PolicyDecision(allowed=False, rule="employees_only",
                              reason="Company Brain answers Acme employees only.")
    q = question.lower()
    if re.search(r"\b(salar(y|ies)|payslips?|compensation)\b", q):
        return PolicyDecision(allowed=False, rule="no_compensation",
                              reason="Compensation questions go to HR directly, not to Company Brain.")
    if re.search(r"\b(passwords?|api keys?|credentials?|secrets?|tokens?)\b", q):
        return PolicyDecision(allowed=False, rule="no_credentials",
                              reason="Company Brain never handles passwords, keys or other credentials.")
    return PolicyDecision(allowed=True, rule="ok")


def tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS and len(w) > 1}


def keyword_score(query_terms: set[str], text: str) -> float:
    """Share of the query's terms that appear in the text: 0.0 .. 1.0."""
    if not query_terms:
        return 0.0
    return round(len(query_terms & tokenize(text)) / len(query_terms), 4)


def rank(query: str, passages: list[Passage], k: int) -> list[Passage]:
    """Score, drop zeros, sort by score (then doc_id, for determinism), one passage per doc_id, keep k."""
    terms = tokenize(query)
    scored = [p.model_copy(update={"score": keyword_score(terms, p.title + " " + p.text)}) for p in passages]
    scored = [p for p in scored if p.score > 0]
    scored.sort(key=lambda p: (-p.score, p.doc_id))
    seen: set[str] = set()
    unique = [p for p in scored if not (p.doc_id in seen or seen.add(p.doc_id))]
    return unique[: max(0, k)]


def build_prompt(question: str, passages: list[Passage]) -> str:
    docs = "\n".join(f'<document id="{p.doc_id}" title="{p.title}">\n{p.text}\n</document>' for p in passages)
    return f"<documents>\n{docs}\n</documents>\n\n<question>{question}</question>"


def parse_citations(text: str, allowed: set[str]) -> list[str]:
    """[doc_id] markers in the reply, in order, without duplicates, and ONLY ids
    that were actually retrieved: a citation to anything else is invented."""
    out: list[str] = []
    for c in re.findall(r"\[([^\[\]\s]+)\]", text):
        if c in allowed and c not in out:
            out.append(c)
    return out


def degraded_text(passages: list[Passage]) -> str:
    titles = "; ".join(f"{p.title} ({p.doc_id})" for p in passages)
    return ("The answer service is temporarily unavailable. "
            + (f"These documents look relevant: {titles}." if titles else "Please try again in a few minutes."))
