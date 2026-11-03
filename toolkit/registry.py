"""A tool registry: one place that knows every tool's name, description, input
model (Pydantic), implementation, and safety properties.

The model only ever sees name + description + JSON Schema (via `.tools()`).
Everything else (the function, side_effect, untrusted_output, timeout) stays on
YOUR side, where the executor uses it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type

from pydantic import BaseModel

from llmkit.tools import tool_from_model
from llmkit.types import Tool


class ToolError(Exception):
    """An EXPECTED failure whose message is written for the model: what went wrong
    and what to try next (e.g. "No employee with email x. Try the full name.").
    The executor turns it into an is_error result with exactly this text."""


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: Type[BaseModel]
    fn: Callable[[Any], Any]  # called with the validated input model instance
    side_effect: bool = False  # changes the world (writes, sends, grants): needs confirmation and idempotency
    untrusted_output: bool = False  # returns text written by people outside your control (documents, emails, web)
    timeout_s: Optional[float] = None  # overrides the executor default
    strict: bool = True

    def as_tool(self, strict: Optional[bool] = None) -> Tool:
        return tool_from_model(self.input_model, name=self.name, description=self.description,
                               strict=self.strict if strict is None else strict)


@dataclass
class Registry:
    specs: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> ToolSpec:
        if spec.name in self.specs:
            raise ValueError(f"tool {spec.name!r} is already registered")
        spec.as_tool()  # validates the name and description early
        self.specs[spec.name] = spec
        return spec

    def tool(self, name: str, description: str, input_model: Type[BaseModel], **kw):
        """Decorator form: @registry.tool("lookup_employee", "...", LookupEmployeeInput)."""
        def deco(fn):
            self.register(ToolSpec(name, description, input_model, fn, **kw))
            return fn
        return deco

    def get(self, name: str) -> Optional[ToolSpec]:
        return self.specs.get(name)

    def names(self) -> list[str]:
        return list(self.specs)

    def tools(self, names: Optional[list[str]] = None, strict: Optional[bool] = None) -> list[Tool]:
        """llmkit Tool definitions to put in ChatRequest.tools. Pass `names` to expose
        only a subset: least privilege starts with not offering a tool at all."""
        chosen = names or self.names()
        return [self.specs[n].as_tool(strict) for n in chosen]

    def subset(self, names: list[str]) -> "Registry":
        return Registry({n: self.specs[n] for n in names})

    def with_descriptions(self, descriptions: dict[str, str], renames: Optional[dict[str, str]] = None) -> "Registry":
        """A copy with other descriptions (and optionally names): for description A/B tests."""
        renames = renames or {}
        out = Registry()
        for n, s in self.specs.items():
            new = renames.get(n, n)
            out.register(ToolSpec(new, descriptions.get(n, s.description), s.input_model, s.fn, s.side_effect,
                                  s.untrusted_output, s.timeout_s, s.strict))
        return out
