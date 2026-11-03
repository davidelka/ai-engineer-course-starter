"""Spec linter: the reference for exercise 2 of lesson 6.

A requirement an agent can implement reliably has an id (so tests and code can point at it),
a statement in EARS form with SHALL, acceptance criteria in GIVEN/WHEN/THEN form, and no
word that a test cannot check. Non-functional requirements carry a number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .spec import Spec

# Words and phrases a test cannot check. Matched case-insensitively on word boundaries.
VAGUE_WORDS = [
    "fast", "quickly", "slow", "simple", "easy", "easily", "user-friendly", "intuitive",
    "appropriate", "appropriately", "relevant", "reasonable", "robust", "scalable", "efficient",
    "flexible", "gracefully", "properly", "seamless", "seamlessly", "as needed", "if possible",
    "etc", "and so on", "some", "several", "many", "normal", "usually", "generally", "tbd",
    "best", "optimal", "adequate", "sufficient",
]
WEAK_MODALS = ["should", "may", "might", "could"]
EARS_STARTS = ("the ", "when ", "while ", "if ", "where ")


@dataclass(frozen=True)
class Finding:
    rule: str  # missing-id | duplicate-id | missing-statement | not-ears | weak-modal | no-criteria
    #           criterion-not-gwt | vague-word | nfr-not-measurable
    req_id: Optional[str]
    message: str
    severity: str = "error"  # "error" | "warning"


def find_words(text: str, words: list[str]) -> list[str]:
    """Words from `words` that occur in text, in list order, each once."""
    out = []
    for w in words:
        if re.search(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", text, re.I):
            out.append(w)
    return out


def is_gwt(text: str) -> bool:
    """GIVEN, WHEN and THEN all present as words, in that order."""
    pos = -1
    for kw in ("given", "when", "then"):
        m = re.search(r"\b" + kw + r"\b", text[pos + 1:], re.I)
        if not m:
            return False
        pos = pos + 1 + m.start()
    return True


def lint_spec(spec: Spec) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for r in spec.requirements:
        rid = r.id
        if rid is None:
            out.append(Finding("missing-id", None, f'requirement "{r.title}" has no REQ-/NFR- id'))
        elif rid in seen:
            out.append(Finding("duplicate-id", rid, f"{rid} is used more than once"))
        else:
            seen.add(rid)

        st = r.statement.strip()
        if not st:
            out.append(Finding("missing-statement", rid, "no **Statement:** line"))
        else:
            if not re.search(r"\bshall\b", st, re.I) or not st.lower().startswith(EARS_STARTS):
                out.append(Finding("not-ears", rid, "statement must use an EARS form with SHALL "
                                                    "(THE SYSTEM / WHEN / WHILE / IF / WHERE ... SHALL ...)"))
            for w in find_words(st, WEAK_MODALS):
                out.append(Finding("weak-modal", rid, f'"{w}" in statement: use SHALL', "warning"))
            for w in find_words(st, VAGUE_WORDS):
                out.append(Finding("vague-word", rid, f'"{w}" in statement'))
            if r.kind == "non-functional" and not re.search(r"\d", st):
                out.append(Finding("nfr-not-measurable", rid, "non-functional requirement without a number"))

        if not r.criteria:
            out.append(Finding("no-criteria", rid, "no acceptance criteria"))
        for c in r.criteria:
            label = c.id or "criterion"
            if not is_gwt(c.text):
                out.append(Finding("criterion-not-gwt", rid, f"{label} is not GIVEN ... WHEN ... THEN ..."))
            for w in find_words(c.text, VAGUE_WORDS):
                out.append(Finding("vague-word", rid, f'"{w}" in {label}'))
    return out
