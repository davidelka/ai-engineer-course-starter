"""Memory WITHIN one run (lesson 15, exercise 7 asks you to write clear_old_tool_results).

Every step resends the whole conversation, so tool results pile up: a run of 10 steps
pays for the first result 10 times. Two standard answers:

  clear_old_tool_results   keep the last `keep` tool-result turns verbatim and replace
                           the content of older results with a short placeholder. The
                           ToolCall/ToolResult ids stay, so the conversation stays valid
                           for every provider. Anthropic offers the same thing server
                           side (context editing, strategy clear_tool_uses_20250919).
  Scratchpad               a `note` tool the model calls to save the few facts it will
                           need later. Notes live in the system prompt, so they survive
                           clearing. Without notes, clearing makes the model re-fetch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, Field

from llmkit.tools import tool_from_model
from llmkit.types import Message, Tool, ToolResult

CLEARED_PREFIX = "[cleared:"


def placeholder(result: ToolResult) -> str:
    return (f"{CLEARED_PREFIX} earlier result of {result.name or 'a tool'} removed to save context "
            f"({len(result.text)} chars). Call the tool again only if you really need it.]")


def is_cleared(result: ToolResult) -> bool:
    return isinstance(result.content, str) and result.content.startswith(CLEARED_PREFIX)


def clear_old_tool_results(messages: list[Message], keep: int) -> tuple[list[Message], int]:
    """Return (new_messages, how_many_results_were_cleared_now).

    - A "tool-result turn" is a user Message whose content has at least one ToolResult.
    - The last `keep` such turns stay as they are. In every older one, each ToolResult
      that is not cleared yet gets content = placeholder(result); call_id, name and
      is_error stay the same (the ids MUST stay, or the provider rejects the history).
    - Other parts (text blocks) and other messages are kept as they are.
    - The input list and its messages are NOT modified: build new Message objects for
      the turns you change (shallow copies are fine for the rest).
    - keep <= 0 clears every tool-result turn. Already-cleared results are not counted again.
    """
    turns = [i for i, m in enumerate(messages) if m.role == "user" and m.tool_results]
    old = set(turns[:-keep]) if keep > 0 else set(turns)
    out: list[Message] = []
    cleared = 0
    for i, m in enumerate(messages):
        if i not in old:
            out.append(m)
            continue
        parts = []
        for p in m.content:  # type: ignore[union-attr]
            if isinstance(p, ToolResult) and not is_cleared(p):
                parts.append(ToolResult(p.call_id, placeholder(p), is_error=p.is_error, name=p.name))
                cleared += 1
            else:
                parts.append(p)
        out.append(Message(m.role, parts, raw=m.raw, raw_provider=m.raw_provider))
    return out, cleared


# ---------------------------------------------------------------- scratchpad
NOTE_TOOL = "note"


class NoteInput(BaseModel):
    text: str = Field(description="One short fact to remember, e.g. \"Dana Levi's manager: Michal Ben-David (E005)\"")


NOTE_DESCRIPTION = ("Save one short fact you will need later in this task (an id, a manager, a policy route). "
                    "Notes stay visible for the whole task, even after old tool results are removed to save "
                    "space. It has no side effects. You may call it in the same turn as other tools.")


def note_tool() -> Tool:
    return tool_from_model(NoteInput, name=NOTE_TOOL, description=NOTE_DESCRIPTION, strict=True)


@dataclass
class Scratchpad:
    max_notes: int = 30
    notes: list[str] = field(default_factory=list)

    def add(self, text: str) -> str:
        text = " ".join(str(text).split())[:300]
        if text and text not in self.notes:
            self.notes.append(text)
            self.notes = self.notes[-self.max_notes:]
        return f"Saved. {len(self.notes)} note(s) kept."

    def render(self) -> Optional[str]:
        if not self.notes:
            return None
        return "<notes>\n" + "\n".join(f"- {n}" for n in self.notes) + "\n</notes>"
