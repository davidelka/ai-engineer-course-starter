"""Reference for exercise 1: break an Anthropic Messages request into context layers.

Exercise 1 asks you to write your own layer_report in mine.py. Don't read on before
your tests pass.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

LAYERS = ("tools", "system", "history", "retrieved", "user_turn")
DOCS_RE = re.compile(r"<documents>.*?</documents>", re.S)


@dataclass
class Layer:
    name: str
    tokens: int = 0
    cached_tokens: int = 0  # the part of this layer that sits inside the cached prefix


def _blocks(content) -> list[tuple[str, bool]]:
    """str or list of content blocks -> [(text, has_cache_control)]."""
    if isinstance(content, str):
        return [(content, False)]
    out = []
    for b in content or []:
        text = b.get("text", "") if b.get("type", "text") == "text" else json.dumps(b, ensure_ascii=False)
        out.append((text, "cache_control" in b))
    return out


def tool_text(tool: dict) -> str:
    return json.dumps({k: v for k, v in tool.items() if k != "cache_control"}, ensure_ascii=False)


def layer_report(body: dict, count: Callable[[str], int]) -> list[Layer]:
    # 1) Flatten the request into pieces in the order the API reads it:
    #    (layer, text, ends_with_breakpoint). A block of the last user message is split
    #    into its <documents> parts (retrieved) and the rest (user_turn).
    pieces: list[tuple[str, str, bool]] = []
    for tool in body.get("tools") or []:
        pieces.append(("tools", tool_text(tool), "cache_control" in tool))
    system = body.get("system") or ""
    for text, bp in (_blocks(system) if system else []):
        pieces.append(("system", text, bp))
    messages = body.get("messages") or []
    for i, m in enumerate(messages):
        last = i == len(messages) - 1
        for text, bp in _blocks(m.get("content")):
            if not last:
                pieces.append(("history", text, bp))
                continue
            docs = DOCS_RE.findall(text)
            rest = DOCS_RE.sub("", text)
            parts = [("retrieved", d) for d in docs] + [("user_turn", rest)]
            for k, (layer, t) in enumerate(parts):
                # the breakpoint belongs to the block, so mark it on the block's last piece
                pieces.append((layer, t, bp and k == len(parts) - 1))
    # 2) The cached prefix ends at the last breakpoint; top-level cache_control means
    #    automatic caching: the breakpoint goes on the last block, so all of it is prefix.
    marks = [i for i, p in enumerate(pieces) if p[2]]
    if isinstance(body.get("cache_control"), dict) and pieces:
        marks.append(len(pieces) - 1)
    end = max(marks) if marks else -1
    # 3) Count.
    report = {name: Layer(name) for name in LAYERS}
    for i, (layer, text, _) in enumerate(pieces):
        n = count(text)
        report[layer].tokens += n
        if i <= end:
            report[layer].cached_tokens += n
    return [report[name] for name in LAYERS]
