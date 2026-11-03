"""Tool-use helpers (lesson 14). The wire mapping lives in each provider adapter;
this module only builds Tool definitions and small conveniences around them.

    from pydantic import BaseModel, Field
    from llmkit import LLM, ChatRequest, Message
    from llmkit.tools import tool_from_model

    class LookupEmployee(BaseModel):
        email: str = Field(description="Work email, e.g. dana.levi@acme.example")

    tool = tool_from_model(LookupEmployee, name="lookup_employee",
                           description="Look up one Acme employee by work email ...", strict=True)
    req = ChatRequest(messages=[Message("user", "Who is Dana Levi's manager?")], tools=[tool])
    r = LLM("anthropic:claude-haiku-5-5").complete(req)
    r.tool_calls  # [ToolCall(id='toolu_...', name='lookup_employee', arguments={'email': ...})]

See llmkit/TOOLS.md for the full round trip.
"""

from __future__ import annotations

import json
import re
from typing import Optional, Type

from pydantic import BaseModel

from .types import Tool

NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")  # the intersection of the three providers' rules


def tool_from_model(model: Type[BaseModel], *, name: Optional[str] = None, description: Optional[str] = None,
                    strict: bool = False, cache: Optional[str] = None) -> Tool:
    """A Pydantic input model -> a provider-neutral Tool.

    name defaults to the model name in snake_case; description defaults to the
    model's docstring. The schema is model_json_schema() as is: with strict=True each
    adapter applies llmkit.schema.strict_schema for its provider at send time.
    """
    name = name or re.sub(r"(?<!^)(?=[A-Z])", "_", model.__name__).lower()
    if not NAME_RE.match(name):
        raise ValueError(f"tool name {name!r} must match {NAME_RE.pattern} (portable across providers)")
    desc = description if description is not None else (model.__doc__ or "").strip()
    if not desc:
        raise ValueError(f"tool {name!r} needs a description: it is the prompt that tells the model when to use it")
    schema = model.model_json_schema()
    schema.pop("title", None)
    return Tool(name=name, description=desc, input_schema=schema, strict=strict, cache=cache)  # type: ignore[arg-type]


def definition_size(tools: list[Tool]) -> int:
    """Rough token count of the tool definitions (chars / 4). Tool definitions are
    part of the prompt on every call, so they cost input tokens every time."""
    text = json.dumps([{"name": t.name, "description": t.description, "input_schema": t.input_schema}
                       for t in tools], ensure_ascii=False)
    return max(1, round(len(text) / 4))
