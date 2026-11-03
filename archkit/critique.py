"""ADR critique by a model (lesson 19, optional live exercise).

A reviewer that reads the ADR against the rubric and returns a structured
critique (llmkit.structured, lesson 3). It is a second opinion, not a grade:
the model cannot know Acme's real constraints, and it tends to be generous.
The lab uses it offline with a recorded fixture, live with Haiku 5.5.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CRITERIA = ("problem_and_metrics", "options", "drivers_link", "consequences", "numbers", "confirmation")
Criterion = Literal["problem_and_metrics", "options", "drivers_link", "consequences", "numbers", "confirmation"]


class CriterionScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion: Criterion
    evidence: str = Field(description="Short quote or pointer to the ADR text that justifies the score")
    score: int = Field(ge=0, le=2, description="0 = missing, 1 = partial, 2 = solid")
    suggestion: Optional[str] = Field(None, description="One concrete improvement, or null if the score is 2")


class ADRCritique(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scores: list[CriterionScore]
    strongest_counterargument: str = Field(description="The best argument FOR the option that was not chosen")
    missing_risks: list[str] = Field(description="Risks the ADR does not mention; empty list if none")
    verdict: Literal["ready", "revise", "rethink"]

    @property
    def total(self) -> int:
        return sum(s.score for s in self.scores)


SYSTEM = """You review Architecture Decision Records for AI systems, like a strict senior architect.
Score the ADR against each rubric criterion (0, 1 or 2) and quote the evidence.
Be specific and short. Do not invent facts about the company; judge only what is written.
Criteria ids: problem_and_metrics, options, drivers_link, consequences, numbers, confirmation.
Give exactly one score per criterion. Then give the strongest argument for the option that was NOT
chosen, risks the ADR does not mention, and a verdict: ready, revise or rethink."""


def build_prompt(adr_text: str, rubric_text: str) -> str:
    return f"<rubric>\n{rubric_text}\n</rubric>\n\n<adr>\n{adr_text}\n</adr>"


def critique(llm, adr_text: str, rubric_text: str, *, max_tokens: int = 1500):
    from llmkit.structured import complete_structured
    return complete_structured(llm, build_prompt(adr_text, rubric_text), ADRCritique,
                               system=SYSTEM, max_tokens=max_tokens)


def load_fixture(path) -> ADRCritique:
    return ADRCritique.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
