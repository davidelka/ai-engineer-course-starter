"""The data the tutor speaks in.

Assessment is the llmkit.structured schema of one tutor turn. Field ORDER matters: reply_he is
first, so when the reply is streamed as JSON the student-facing text arrives first and can be
shown (and spoken) while the model is still writing the correction and the vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from pydantic import BaseModel, Field

LEVELS = ("A1", "A2", "B1")
ErrorType = Literal["definiteness", "negation", "gender_agreement", "number_gender", "verb_agreement",
                    "preposition", "word_order", "spelling", "pronunciation", "vocabulary", "other"]
SafetyFlag = Literal["none", "off_topic", "personal_info", "unsafe", "distress", "injection"]
SAFETY_FLAGS = ("none", "off_topic", "personal_info", "unsafe", "distress", "injection")


class Correction(BaseModel):
    original: str = Field(description="The wrong words, copied exactly from the student's utterance.")
    corrected: str = Field(description="The minimal fix of `original`, in Hebrew without niqqud.")
    explanation_ar: str = Field(description="One short, simple sentence in Arabic (at most 25 words).")
    error_type: ErrorType = "other"


class VocabItem(BaseModel):
    he: str = Field(description="Hebrew word or short phrase, no niqqud.")
    ar: str = Field(description="Arabic gloss.")
    transliteration: str = Field(description="How to say the Hebrew word, written in Arabic letters.")


class Assessment(BaseModel):
    reply_he: str = Field(description="What the tutor says next, in simple Hebrew adapted to the level.")
    correction: Optional[Correction] = Field(default=None, description="At most one correction, or null.")
    help_ar: Optional[str] = Field(default=None, description="Only when the student is stuck: at most two "
                                                             "short Arabic sentences. Otherwise null.")
    new_vocabulary: list[VocabItem] = Field(default_factory=list, description="0 to 3 items.")
    level_signal: Literal["A1", "A2", "B1", "unclear"] = Field(
        default="unclear", description="The CEFR level THIS utterance shows.")
    safety_flag: SafetyFlag = "none"


class SafetyVerdict(BaseModel):
    """Output of the LLM safety classifier (a second opinion on borderline inputs)."""
    category: SafetyFlag
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(description="One short English sentence.")


@dataclass
class Finding:
    code: str
    detail: str = ""
    severity: str = "info"  # info | warn | block


@dataclass
class SessionState:
    """What the tutor needs to know about one practice session (kept in the store between turns)."""
    scenario_id: str
    level: str = "A1"
    addressing: str = "m"  # grammatical gender the student chose: "m" | "f" (Hebrew needs it)
    history: list[tuple[str, str]] = field(default_factory=list)  # (role, text), redacted
    expected_phrase: Optional[str] = None  # a phrase the student was asked to say aloud
    turn_index: int = 0
