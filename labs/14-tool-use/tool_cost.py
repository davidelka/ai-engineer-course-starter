"""Exercise 2: what the tool definitions cost, and what strict mode changes in each schema.

    python labs/14-tool-use/tool_cost.py                 # offline: schemas, strict notes, approximate tokens
    python labs/14-tool-use/tool_cost.py --live          # + exact counts from Anthropic count_tokens (free)
    python labs/14-tool-use/tool_cost.py --show check_policy --provider openai

Tool definitions are sent on EVERY call of the conversation, before the messages.
Anthropic also adds a tool-use system prompt when tools are present (286 tokens for
auto/none, 406 for any/tool on Haiku 5.5, per the docs; --live measures it).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

import _lab  # noqa: F401
from _lab import ROOT
from llmkit import load_dotenv
from llmkit.pricing import PRICES
from llmkit.schema import strict_schema
from llmkit.tools import definition_size
from toolkit import acme_registry

QUESTION = "Who would approve a Figma editor seat for dana.levi@acme.example?"


def count_live(key: str, tools: list, tool_choice: dict | None = None) -> int:
    body = {"model": "claude-haiku-5-5", "messages": [{"role": "user", "content": QUESTION}]}
    if tools:
        body["tools"] = tools
    if tool_choice:
        body["tool_choice"] = tool_choice
    r = httpx.post("https://api.anthropic.com/v1/messages/count_tokens", timeout=30, json=body,
                   headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    r.raise_for_status()
    return r.json()["input_tokens"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--show", help="print one tool's schema as each provider receives it in strict mode")
    ap.add_argument("--provider", default="anthropic", choices=["anthropic", "openai", "gemini"])
    a = ap.parse_args()
    reg = acme_registry()
    tools = reg.tools(strict=False)

    print("Tool definitions (approximate tokens = characters / 4):")
    for t in tools:
        print(f"  {t.name:24} ~{definition_size([t]):4d} tokens   description: {len(t.description)} chars")
    total = definition_size(tools)
    print(f"  {'ALL SIX':24} ~{total:4d} tokens\n")

    print("What strict mode changes, per provider:")
    for provider in ("anthropic", "openai", "gemini"):
        notes = [n for t in tools for n in strict_schema(t.input_schema, provider)[1]]
        moved = [n for n in notes if "moved" in n]
        print(f"  {provider:9} {len(notes)} changes ({len(moved)} constraints moved into descriptions)")
        for n in moved[:4]:
            print(f"            - {n}")
    if a.show:
        spec = reg.get(a.show) or sys.exit(f"unknown tool {a.show}")
        print(f"\n{a.show} as {a.provider} receives it (strict):")
        print(json.dumps(strict_schema(spec.as_tool().input_schema, a.provider)[0], indent=2, ensure_ascii=False))

    price = PRICES["claude-haiku-5-5"]["input"]
    per_call = (total + 286) * price / 1e6
    print(f"\nRough cost with Haiku 5.5 (${price}/M input): ~${per_call:.6f} per call for the definitions alone;"
          f" a 4-round loop sends them 4 times: ~${per_call * 4:.5f}. Prompt caching (lesson 4) cuts this:"
          " tools are the first thing in the cached prefix.")

    if a.live:
        load_dotenv(str(ROOT / ".env"))
        key = os.environ.get("ANTHROPIC_API_KEY") or sys.exit("ANTHROPIC_API_KEY is not set")
        wire = [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools]
        base = count_live(key, [])
        one = count_live(key, wire[:1])
        six = count_live(key, wire)
        forced = count_live(key, wire, {"type": "any"})
        print("\nLive, Anthropic count_tokens (free):")
        print(f"  no tools:             {base}")
        print(f"  1 tool:               {one}   (+{one - base}: tool prompt + 1 definition)")
        print(f"  6 tools:              {six}   (+{six - base})")
        print(f"  6 tools, choice=any:  {forced}   (+{forced - six} vs auto)")
        print(f"  approximation above said ~{total} for the six definitions; compare with {six - one + definition_size(tools[:1])}.")


if __name__ == "__main__":
    main()
