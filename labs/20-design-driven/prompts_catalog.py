"""The answer prompt's version history, with the output schema the calling code reads.
Used by exercise 6 (registry_demo.py and tests/test_ex6_registry.py).

The story, in order:
  1.0.0  first version: JSON {text, citations, status in answered|no_context}
  1.0.1  a typo fixed in the prompt text, same schema               -> compatible
  1.1.0  asks the model for a confidence score, new OPTIONAL field  -> compatible
  1.2.0  adds status "partial"                                      -> BREAKING: a new enum value
  2.0.0  the same change, published as a new major                  -> fine, callers pinned to "1" keep 1.1.0
  2.1.0  renames citations -> sources                               -> BREAKING inside major 2
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from designkit.types import PromptVersion

BASE = ("You are Company Brain, Acme's internal assistant. Answer using ONLY the documents provided "
        "and cite each fact as [doc_id]. Reply with a JSON object.")


class OutV1(BaseModel):
    text: str
    citations: list[str]
    status: Literal["answered", "no_context"]


class OutV1_1(OutV1):
    confidence: Optional[float] = None  # optional: old readers simply ignore it


class OutPartial(BaseModel):
    text: str
    citations: list[str]
    status: Literal["answered", "no_context", "partial"]  # code that does `match status` has no case for it
    confidence: Optional[float] = None


class OutRenamed(BaseModel):
    text: str
    sources: list[str]
    status: Literal["answered", "no_context", "partial"]
    confidence: Optional[float] = None


class OutNullableText(BaseModel):
    text: Optional[str]  # the reader does text.strip() and crashes on None
    citations: list[str]
    status: Literal["answered", "no_context"]


def pv(version: str, template: str, model: type[BaseModel]) -> PromptVersion:
    return PromptVersion(name="answer", version=version, template=template, output_schema=model.model_json_schema())


V1_0_0 = pv("1.0.0", BASE + " If the documents do not contian the answer, say so.", OutV1)
V1_0_1 = pv("1.0.1", BASE + " If the documents do not contain the answer, say so.", OutV1)
V1_1_0 = pv("1.1.0", BASE + " If the documents do not contain the answer, say so. "
                            "Add confidence between 0 and 1.", OutV1_1)
V1_2_0_BAD = pv("1.2.0", BASE + " Use status partial when the documents answer only part of the question. "
                                "Add confidence between 0 and 1.", OutPartial)
V2_0_0 = pv("2.0.0", V1_2_0_BAD.template, OutPartial)
V2_1_0_BAD = pv("2.1.0", V1_2_0_BAD.template.replace("[doc_id]", "a source id"), OutRenamed)

HISTORY = [V1_0_0, V1_0_1, V1_1_0, V1_2_0_BAD, V2_0_0, V2_1_0_BAD]
