"""JSON Schema transforms for providers' strict modes (lessons 3 and 14).

Used for both native structured output (llmkit.structured) and strict tool
definitions (llmkit tools with strict=True). Pure functions, no I/O, no imports
from the rest of llmkit, so provider adapters can use them too.
"""

from __future__ import annotations

import copy
from typing import Any

# Keywords each provider rejects (400) or silently ignores in native/strict mode.
# Sources (Oct 2026): platform.claude.com structured-outputs, developers.openai.com
# structured-outputs, ai.google.dev structured output. Conservative on purpose:
# anything stripped here is still enforced by Pydantic on our side.
# Strict tool use on Anthropic compiles input_schema with the SAME pipeline as
# structured outputs (platform.claude.com strict-tool-use, Nov 2026), so the same
# limits apply to tool schemas.
UNSUPPORTED: dict[str, set[str]] = {
    # "pattern": the docs say simple patterns work, but in a live test (Oct 2026) even
    # ^[^@]+@[^@]+$ on a nullable field returned 400 "Schema is too complex." Measured, not assumed.
    "anthropic": {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
                  "minLength", "maxLength", "maxItems", "uniqueItems", "minProperties", "maxProperties",
                  "pattern"},
    "openai": {"minLength", "maxLength", "uniqueItems", "minProperties", "maxProperties"},
    "gemini": {"minLength", "maxLength", "pattern", "uniqueItems", "minProperties", "maxProperties",
               "exclusiveMinimum", "exclusiveMaximum", "multipleOf"},
}
DROP_ALWAYS = {"title", "default"}  # noise; and "default" conflicts with all-required strict schemas


def strict_schema(schema: dict, provider: str, *, keep_root_title: bool = True) -> tuple[dict, list[str]]:
    """Any JSON Schema (dict) -> the version a provider accepts in strict mode.

    - every object gets additionalProperties: false
    - every property becomes required (nullable fields stay nullable, so
      "absent" is expressed as null, which strict modes require)
    - unsupported keywords are removed and appended to the description
    Returns (schema, notes); notes list every change, for inspection.
    The input is not modified.
    """
    schema = copy.deepcopy(schema)
    banned = UNSUPPORTED.get(provider, set())
    notes: list[str] = []

    def walk(node: Any, path: str) -> Any:
        if isinstance(node, list):
            return [walk(x, path) for x in node]
        if not isinstance(node, dict):
            return node
        moved = {k: node[k] for k in list(node) if k in banned}
        for k in moved:
            del node[k]
        if moved:
            hint = ", ".join(f"{k}={v}" for k, v in moved.items())
            node["description"] = (node.get("description", "") + f" (constraints: {hint})").strip()
            notes.append(f"{path or '/'}: moved {hint} into description (not enforced by {provider})")
        for k in DROP_ALWAYS & set(node):
            if k == "title" and path == "" and keep_root_title:
                continue
            del node[k]
        if node.get("type") == "object" or "properties" in node:
            node["additionalProperties"] = False
            props = node.get("properties", {})
            missing = [p for p in props if p not in node.get("required", [])]
            if missing:
                notes.append(f"{path or '/'}: made required (nullable stays nullable): {', '.join(missing)}")
            node["required"] = list(props)
        for k, v in list(node.items()):
            if k == "properties":
                node[k] = {name: walk(sub, f"{path}/{name}") for name, sub in v.items()}
            elif k in ("$defs", "definitions"):
                node[k] = {name: walk(sub, f"#/{k}/{name}") for name, sub in v.items()}
            elif isinstance(v, (dict, list)):
                node[k] = walk(v, path)
        return node

    return walk(schema, ""), notes
