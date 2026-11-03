"""LLM spec review (lesson 6, exercise 7): ask a model where a spec is ambiguous.

A linter finds vague WORDS. A reviewer model can find vague BEHAVIOR: two rules that
overlap, a case no rule covers, a field the contract has and the spec never mentions.
It can also invent problems and misquote the spec, so every finding is grounded:
its quote must appear in the spec, and its requirement id must exist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

REVIEW_SYSTEM = """You review software specifications before an AI coding agent implements them.

The test of a good spec: two competent engineers who never talk to each other, one writing the
code and one writing the tests, end up with the same observable behavior, without asking anyone.

Report only problems that break that test:
- ambiguous: the text allows two different behaviors.
- untestable: an acceptance criterion cannot be checked by an automated test as written.
- missing_case: an input or state the rules do not cover, or a rule no acceptance criterion exercises.
- contradiction: two statements require different behavior for the same input.
- inconsistent_with_contract: the spec and the interface contract disagree, or the contract has
  a field or status the spec never explains.
- missing_requirement: behavior the intent clearly needs that no requirement states.

Do not report style, formatting, wording preferences or things the spec lists as out of scope.
Report at most 10 findings, the most consequential first. For each finding, copy the exact words
from the spec into `quote` (verbatim, at most 200 characters, no paraphrase), explain the two
behaviors an implementer could choose between, then classify it, then propose a rewrite that
removes the ambiguity. If the spec has no such problems, return an empty list."""


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_id: Optional[str] = Field(
        None, description="The REQ-n or NFR-n id the problem is in, or null for the spec as a whole")
    quote: str = Field(description="Exact words copied from the spec, verbatim, at most 200 characters")
    explanation: str = Field(description="The different behaviors an implementer could choose, in 1-3 sentences")
    problem: Literal["ambiguous", "untestable", "missing_case", "contradiction",
                     "inconsistent_with_contract", "missing_requirement"]
    suggested_rewrite: str = Field(description="Replacement text that removes the problem")


class SpecReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[ReviewFinding]


def review_prompt(spec_text: str, contract_text: str = "") -> str:
    parts = ["<spec>\n" + spec_text.strip() + "\n</spec>"]
    if contract_text:
        parts.append("<interface_contract>\n" + contract_text.strip() + "\n</interface_contract>")
    parts.append("Review the spec. Return the findings.")
    return "\n\n".join(parts)


def _norm(s: str) -> str:
    return " ".join(s.replace("`", "").split()).lower()


@dataclass
class Grounded:
    kept: list[ReviewFinding]
    dropped: list[tuple[ReviewFinding, str]]


def ground_findings(review: SpecReview, source_text: str, known_ids: list[str]) -> Grounded:
    """Keep a finding only if its quote is really in the sources and its id really exists.

    source_text is what the reviewer saw: the spec, plus the contract when it was sent.
    Matching ignores case, backticks and line wrapping, since specs wrap long sentences."""
    hay = _norm(source_text)
    kept, dropped = [], []
    for f in review.findings:
        if f.requirement_id and f.requirement_id not in known_ids:
            dropped.append((f, f"unknown requirement id {f.requirement_id}"))
        elif not f.quote.strip() or _norm(f.quote) not in hay:
            dropped.append((f, "the quote is not in the spec or the contract"))
        else:
            kept.append(f)
    return Grounded(kept, dropped)


def ids_in(text: str) -> list[str]:
    return sorted(set(re.findall(r"\b(?:REQ|NFR)-\d+\b", text)))
