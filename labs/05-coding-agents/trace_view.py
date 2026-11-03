"""Exercise 1: look at the agent loop in a real Claude Code transcript.

    python labs/05-coding-agents/trace_view.py                                  # the recorded example
    python labs/05-coding-agents/trace_view.py results/bugfix-bare-....jsonl    # one of your runs

Prints every step in order: what the model said, each tool call (name + main input), whether
the tool result was an error, and at the end the numbers Claude Code reports for the run.
The recorded example is fixtures/transcript_bugfix_bare.jsonl, a real run of the bugfix task
on the bare workspace with Claude Haiku (see the README for how it was recorded).
"""

from __future__ import annotations

import json
import os
import sys

LAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(LAB)))

from repoguard.transcript import load_events, summarize  # noqa: E402

DEFAULT = os.path.join(LAB, "fixtures", "transcript_bugfix_bare.jsonl")


def steps(events: list[dict]):
    """Yield (kind, text) in transcript order: init, text, tool, result, final."""
    for e in events:
        t = e.get("type")
        if t == "system" and e.get("subtype") == "init":
            tools = e.get("tools") or []
            yield "init", f"model={e.get('model')} tools={len(tools)} mcp_servers={len(e.get('mcp_servers') or [])} permission_mode={e.get('permissionMode')}"
        msg = e.get("message") if isinstance(e.get("message"), dict) else {}
        for b in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
            if not isinstance(b, dict):
                continue
            if t == "assistant" and b.get("type") == "text" and b.get("text", "").strip():
                yield "text", b["text"].strip().replace("\n", " ")[:220]
            elif t == "assistant" and b.get("type") == "tool_use":
                inp = b.get("input") or {}
                main = next((str(inp[k]) for k in ("command", "file_path", "pattern", "path", "skill", "description") if k in inp), json.dumps(inp))
                yield "tool", f"{b.get('name')}: {main.replace(chr(10), ' ')[:160]}"
            elif t == "user" and b.get("type") == "tool_result":
                content = b.get("content")
                if isinstance(content, list):
                    content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                status = "ERROR" if b.get("is_error") else "ok"
                yield "result", f"{status}: {str(content or '').strip().replace(chr(10), ' ')[:140]}"
        if t == "result":
            yield "final", (e.get("result") or "").strip().replace("\n", " ")[:300]


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        events = load_events(f.read())
    marks = {"init": "[start]", "text": "  model:", "tool": "  -> tool", "result": "  <- result", "final": "[final]"}
    n = 0
    for kind, text in steps(events):
        if kind == "tool":
            n += 1
            print(f"{marks[kind]} #{n} {text}")
        else:
            print(f"{marks[kind]} {text}")
    s = summarize(events)
    print("\nnumbers Claude Code reports for this run:")
    for k in ("model", "num_turns", "tool_calls", "tool_counts", "tool_errors", "total_cost_usd", "duration_ms",
              "input_tokens", "output_tokens", "permission_denials", "subtype", "terminal_reason"):
        print(f"  {k:20} {s.get(k)}")


if __name__ == "__main__":
    main()
