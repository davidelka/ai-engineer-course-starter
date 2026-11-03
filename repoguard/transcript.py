"""Read what a Claude Code run did, from `claude -p ... --output-format stream-json --verbose`.

Each stdout line is one JSON event. The ones used here:

  {"type": "system", "subtype": "init", "model": ..., "tools": [...], ...}       first event
  {"type": "assistant", "message": {"content": [{"type": "text", ...},
                                                {"type": "tool_use", "id", "name", "input"}]}}
  {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id",
                                            "content", "is_error"}]}}
  {"type": "result", "subtype": "success", "num_turns", "total_cost_usd", "duration_ms",
   "is_error", "result", "usage", "permission_denials", ...}                        last event

A file written with --output-format json holds only the final result object; summarize()
accepts that too (then there are no tool calls to count).
"""

from __future__ import annotations

import json
from collections import Counter


def load_events(text: str) -> list[dict]:
    text = text.strip()
    if not text:
        return []
    if text.startswith("{") and "\n" not in text:
        try:
            return [json.loads(text)]
        except ValueError:
            return []
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue  # stray warnings on stdout
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def _input_summary(name: str, inp: dict) -> str:
    for key in ("command", "file_path", "notebook_path", "pattern", "path", "url", "description", "prompt", "skill"):
        if isinstance(inp, dict) and key in inp:
            return str(inp[key]).replace("\n", " ")[:160]
    return json.dumps(inp)[:160]


def summarize(events: list[dict]) -> dict:
    """Turn the event list into the numbers the lab records for each run."""
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    calls, errors, texts = [], 0, 0
    for e in events:
        msg = e.get("message") or {}
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if e.get("type") == "assistant" and block.get("type") == "tool_use":
                calls.append({
                    "name": block.get("name", "?"),
                    "input": _input_summary(block.get("name", ""), block.get("input") or {}),
                    "raw": block.get("input") or {},
                    "subagent": e.get("parent_tool_use_id") is not None,
                })
            elif e.get("type") == "assistant" and block.get("type") == "text":
                texts += 1
            elif e.get("type") == "user" and block.get("type") == "tool_result" and block.get("is_error"):
                errors += 1
    usage = result.get("usage") or {}
    return {
        "model": init.get("model") or next(iter(result.get("modelUsage") or {}), None),
        "num_turns": result.get("num_turns"),
        "total_cost_usd": result.get("total_cost_usd"),
        "duration_ms": result.get("duration_ms"),
        "is_error": result.get("is_error"),
        "subtype": result.get("subtype"),
        "terminal_reason": result.get("terminal_reason"),
        "permission_denials": len(result.get("permission_denials") or []),
        "input_tokens": (usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0) + (usage.get("cache_creation_input_tokens") or 0),
        "output_tokens": usage.get("output_tokens"),
        "tool_calls": len(calls),
        "tool_counts": dict(Counter(c["name"] for c in calls)),
        "tool_errors": errors,
        "text_blocks": texts,
        "calls": calls,
        "final_text": (result.get("result") or "")[:2000],
    }
