"""Shared helpers for the lesson 5 tests."""


def event(name: str, tool: str, tool_input: dict, cwd: str = "/tmp/project") -> dict:
    """A hook event shaped like the one Claude Code writes to the hook's stdin."""
    return {
        "session_id": "test",
        "transcript_path": "/tmp/t.jsonl",
        "cwd": cwd,
        "permission_mode": "default",
        "hook_event_name": name,
        "tool_name": tool,
        "tool_input": tool_input,
        "tool_use_id": "toolu_test",
    }
