"""Structured outputs (lesson 3): Pydantic model in, validated object out.

Three layers, each catching what the one before it cannot:

1. The provider's constrained decoding (mode="native"): the reply is JSON
   that matches the schema's SHAPE. Not every JSON Schema keyword is enforced,
   so unsupported constraints are removed from what we send and moved into
   the field description instead.
2. Pydantic validation, against the ORIGINAL model: types, ranges, patterns,
   and the constraints the provider dropped.
3. Your own semantic validators (field_validator / model_validator): rules
   that no schema can express, e.g. "admin access must go to security".

When 2 or 3 fail, the errors are sent back to the model and it tries again
(a "repair" turn), up to max_repairs times.

    from llmkit import LLM
    from llmkit.structured import complete_structured
    res = complete_structured(LLM("anthropic:claude-haiku-5-5"), text, AccessRequest, system=...)
    res.value  # an AccessRequest instance
"""

from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type, Union

from pydantic import BaseModel, ValidationError

from .client import LLM
from .errors import LLMError
from .types import ChatRequest, Message

# The transform itself lives in llmkit/schema.py (lesson 14 reuses it for strict
# tool schemas). Re-exported here so lesson-3 code keeps working unchanged.
from .schema import DROP_ALWAYS, UNSUPPORTED, strict_schema  # noqa: E402,F401


# ---------------------------------------------------------------- schema
def provider_schema(model: Type[BaseModel], provider: str) -> tuple[dict, list[str]]:
    """Pydantic model -> JSON Schema the provider accepts in strict/native mode.

    - every object gets additionalProperties: false
    - every property becomes required (Optional[...] fields stay nullable, so
      "absent" is expressed as null, which strict modes require)
    - unsupported keywords are removed and appended to the description
    Returns (schema, notes) where notes lists what was changed, for inspection.
    """
    return strict_schema(model.model_json_schema(), provider)


def schema_prompt(model: Type[BaseModel]) -> str:
    """For mode='prompt': the schema goes into the instructions, nothing enforces it."""
    return ("Return ONLY a JSON object that matches this JSON Schema. "
            "No prose, no markdown.\n" + json.dumps(model.model_json_schema(), ensure_ascii=False))


# ---------------------------------------------------------------- parsing (reference versions)
FENCE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)```", re.S)


def extract_json(text: str) -> str:
    """Reference implementation. Exercise 3 asks you to write your own in mine.py.

    Return the JSON object inside a model reply: strips ```json fences and prose
    around it; respects braces inside strings. Raises ValueError if none found.
    """
    m = FENCE.search(text)
    if m:
        text = m.group(1)
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found in the reply")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError("JSON object is not closed (truncated reply?)")


def format_errors(exc: Exception, max_errors: int = 8) -> str:
    """Reference implementation. Exercise 4 asks you to write your own in mine.py.

    Turn a parsing/validation failure into short, specific lines the model can act on.
    """
    if isinstance(exc, ValidationError):
        lines = []
        for e in exc.errors()[:max_errors]:
            loc = ".".join(str(p) for p in e["loc"]) or "(root)"
            got = json.dumps(e.get("input"), ensure_ascii=False, default=str)
            got = got if len(got) <= 60 else got[:57] + "..."
            lines.append(f"- {loc}: {e['msg']} (got {got})")
        extra = exc.error_count() - max_errors
        if extra > 0:
            lines.append(f"- ... and {extra} more errors")
        return "\n".join(lines)
    return f"- the reply is not valid JSON: {exc}"


# ---------------------------------------------------------------- the loop
class StructuredError(LLMError):
    """The model did not produce a valid object.

    stage: "refusal" | "truncated" | "invalid" (repairs exhausted)
    """

    def __init__(self, message: str, *, stage: str, last_text: str = "", errors: Optional[list[str]] = None,
                 result: Optional["StructuredResult"] = None, **kw):
        super().__init__(message, kind=f"structured_{stage}", **kw)
        self.stage = stage
        self.last_text = last_text
        self.errors = errors or []
        self.result = result  # usage/cost so far, even on failure


@dataclass
class StructuredResult:
    value: Optional[BaseModel] = None
    text: str = ""  # the raw reply that validated
    attempts: int = 0  # model calls made (1 + repairs)
    errors: list[str] = field(default_factory=list)  # one entry per failed attempt
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0

    @property
    def repairs(self) -> int:
        return max(0, self.attempts - 1)


REPAIR_MSG = ("Your previous reply did not pass validation. Fix exactly these problems and "
              "return ONLY the corrected JSON object:\n{errors}")


def complete_structured(
    llm: LLM,
    prompt: Union[str, ChatRequest],
    model: Type[BaseModel],
    *,
    system: str = "",
    mode: str = "native",  # "native" (constrained decoding) | "prompt" (schema only in the instructions)
    max_repairs: int = 2,
    max_tokens: int = 1024,
    effort: Optional[str] = None,
    extract: Callable[[str], str] = extract_json,
    explain: Callable[[Exception], str] = format_errors,
) -> StructuredResult:
    if isinstance(prompt, ChatRequest):
        req = copy.deepcopy(prompt)
    else:
        req = ChatRequest.from_prompt(prompt, system=system, max_tokens=max_tokens, effort=effort)
    if mode == "native":
        req.response_schema, _ = provider_schema(model, llm.provider.name)
        req.schema_name = model.__name__
    elif mode == "prompt":
        req.system = (req.system + "\n\n" if req.system else "") + schema_prompt(model)
    else:
        raise ValueError("mode must be 'native' or 'prompt'")

    out = StructuredResult()
    t0 = time.perf_counter()
    while True:
        out.attempts += 1
        r = llm.complete(req)  # transport errors and their retries live below this loop
        out.input_tokens += r.usage.input_tokens
        out.output_tokens += r.usage.output_tokens
        out.cost_usd += r.cost_usd or 0.0
        out.latency_s = time.perf_counter() - t0

        if r.stop_reason == "refusal":
            raise StructuredError("the model refused", stage="refusal", last_text=r.text,
                                  provider=llm.provider.name, request_id=r.request_id, result=out)
        if r.stop_reason == "max_tokens":
            # Repairing a cut-off object only cuts it off again: raise max_tokens instead.
            raise StructuredError("reply hit max_tokens before the JSON was complete", stage="truncated",
                                  last_text=r.text, provider=llm.provider.name, request_id=r.request_id,
                                  result=out)
        try:
            value = model.model_validate_json(extract(r.text))
            out.value, out.text = value, r.text
            return out
        except (ValueError, ValidationError) as exc:  # ValidationError is a ValueError subclass too
            problem = explain(exc)
            out.errors.append(problem)
            if out.attempts > max_repairs:
                raise StructuredError(f"no valid object after {out.attempts} attempts", stage="invalid",
                                      last_text=r.text, errors=out.errors, provider=llm.provider.name,
                                      request_id=r.request_id, result=out) from None
            req.messages = req.messages + [Message("assistant", r.text or "(empty reply)"),
                                           Message("user", REPAIR_MSG.format(errors=problem))]
