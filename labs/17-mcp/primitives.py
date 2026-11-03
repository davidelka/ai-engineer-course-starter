"""Exercises 2 and 8: what acme-mcp offers, per primitive, and who decides when each one is used.

    python labs/17-mcp/primitives.py                 # in-process (fast)
    python labs/17-mcp/primitives.py --stdio         # launch `python -m mcpkit` and talk over stdio
    python labs/17-mcp/primitives.py --url http://127.0.0.1:8765/mcp
"""

import argparse
import asyncio
import json
import sys

import _lab  # noqa: F401
from mcp import Client, StdioServerParameters

from llmkit.tools import definition_size
from mcpkit.bridge import mcp_tool_to_llmkit
from mcpkit.server import build_acme_server

p = argparse.ArgumentParser()
g = p.add_mutually_exclusive_group()
g.add_argument("--stdio", action="store_true")
g.add_argument("--url")
p.add_argument("--legacy", action="store_true", help="force the 2025-11-25 initialize handshake")
a = p.parse_args()
target = (StdioServerParameters(command=sys.executable, args=["-m", "mcpkit"]) if a.stdio
          else a.url or build_acme_server())


async def main():
    async with Client(target, mode="legacy" if a.legacy else "auto") as c:
        info = c.server_info
        print(f"server: {info.name} {info.version}   protocol: {c.protocol_version}")
        print(f"instructions ({len(c.instructions or '')} chars): {(c.instructions or '')[:160]}...\n")

        tools = (await c.list_tools()).tools
        print(f"TOOLS ({len(tools)}): the MODEL decides when to call them")
        for t in tools:
            ann = t.annotations
            flags = "read-only" if ann and ann.read_only_hint else "WRITES" if ann else "?"
            print(f"  {t.name:24} {flags:9} {len(t.description or ''):4} chars  {(t.description or '').split('.')[0][:70]}")
        llm_tools = [mcp_tool_to_llmkit(t, server="acme") for t in tools]
        print(f"  -> about {definition_size(llm_tools)} tokens of tool definitions on EVERY model call\n")

        res = (await c.list_resources()).resources
        tmpl = (await c.list_resource_templates()).resource_templates
        print(f"RESOURCES ({len(res)}) + {len(tmpl)} template(s): the APPLICATION (or the user) decides what to attach")
        for r in res[:5]:
            print(f"  {r.uri:38} {r.title}")
        print(f"  ... and {len(res) - 5} more;  templates: {[t.uri_template for t in tmpl]}")
        body = (await c.read_resource("acme://docs/eng-service-catalog")).contents[0].text
        print(f"  read acme://docs/eng-service-catalog -> {len(body)} chars, starts: {body[:60]!r}\n")

        prompts = (await c.list_prompts()).prompts
        print(f"PROMPTS ({len(prompts)}): the USER picks them (in Claude Code: /mcp__acme__<name>)")
        for pr in prompts:
            args = ", ".join(f"{x.name}{'' if x.required else '?'}" for x in (pr.arguments or []))
            print(f"  {pr.name}({args}): {pr.description[:80]}")
        got = await c.get_prompt("summarize-policy", {"doc_id": "hr-vacation-2026"})
        print(f"  get summarize-policy -> {len(got.messages)} messages: "
              f"{[m.content.type for m in got.messages]}")


asyncio.run(main())
