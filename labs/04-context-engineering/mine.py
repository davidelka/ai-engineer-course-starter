"""Your code for lesson 4. Each part is checked by tests in ./tests.

ctxkit/ has reference versions (layers.py, layout.py, compaction.py).
Try not to peek before your tests pass.

    python -m pytest -q labs/04-context-engineering/tests
"""

from __future__ import annotations

import json  # noqa: F401  (you will likely need it)
import re  # noqa: F401
from typing import Callable, Optional

from ctxkit.layers import Layer  # a dataclass: Layer(name, tokens=0, cached_tokens=0)
from ctxkit.layout import HR_INSTRUCTIONS, naive_hr_request  # noqa: F401  (the "before" of exercise 2)
from llmkit import Block, ChatRequest, Message  # noqa: F401

LAYERS = ("tools", "system", "history", "retrieved", "user_turn")


# ------------------------------------------------------------------ exercise 1
def layer_report(body: dict, count: Callable[[str], int]) -> list[Layer]:
    """Break an Anthropic Messages request body into five context layers and count each.

    `body` is the JSON you would POST to /v1/messages, e.g.
        {"tools": [...], "system": "..." or [{"type": "text", "text": "...", "cache_control": {...}}],
         "messages": [{"role": "user", "content": "..." or [blocks]}, ...]}
    `count(text) -> int` counts tokens (tests pass a word counter).

    Return exactly five Layer objects, in this order, even when a layer is empty:
      "tools"      each tool's text = json.dumps(tool without its "cache_control" key, ensure_ascii=False)
      "system"     the system prompt (a string, or the "text" of each block)
      "history"    every message except the last one
      "retrieved"  inside the LAST message (always the user's turn): every <documents>...</documents>
                   span, tags included (one regex: r"<documents>.*?</documents>" with re.S)
      "user_turn"  the rest of the last message, after removing those spans
    Count each piece separately and add up (count(a) + count(b), not count(a + b)).

    Layer.cached_tokens = how many of the layer's tokens sit inside the CACHED PREFIX.
    The API reads tools -> system -> messages, in order. The cached prefix ends at the
    last block that has a "cache_control" key (a tool, a system block, or a message block),
    and includes that block. If the body has a TOP-LEVEL "cache_control" (automatic
    caching), the breakpoint is on the very last block, so everything is prefix.
    No breakpoint at all: every cached_tokens is 0.
    A breakpoint on a block of the last message covers both its retrieved and user_turn parts.
    """
    # TODO(ex1)
    raise NotImplementedError("exercise 1: implement layer_report")


# ------------------------------------------------------------------ exercise 2
def build_hr_request(policies: str, question: str, *, employee: str, today: str,
                     history: Optional[list[Message]] = None, ttl: str = "5m") -> ChatRequest:
    """The lesson-1 HR assistant, rebuilt so its big stable part is cached.

    naive_hr_request() (imported above, from ctxkit/layout.py) is the "before": it starts
    the system prompt with "Today is <date>. You are talking to <name>." and pastes the
    documents AFTER the question in the user message. Nothing in it can be cached.

    Build a ChatRequest where:
      - system is a list of two Blocks: Block(HR_INSTRUCTIONS), then the policies wrapped
        as "<documents>\\n" + policies.strip() + "\\n</documents>".
      - the LAST system block carries the only cache breakpoint: cache=ttl.
      - nothing dynamic is in the system prompt: not the employee, not the date.
      - messages = the history (unchanged, may be None) + one new user message whose text
        has the dynamic context first and the question LAST:
            <context>
            employee: <employee>
            today: <today>
            </context>

            <question>
            <question text>
            </question>
        Use a plain string for this message (no cache breakpoint on it).
      - max_tokens=400.
    Two calls with different questions, employees or dates must produce an IDENTICAL system.
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement build_hr_request")


# ------------------------------------------------------------------ exercise 6
def compact(messages: list[Message], budget: int, count: Callable[[str], int],
            summarize: Callable[[list[Message]], str], keep_last: int = 4) -> list[Message]:
    """Fit a conversation into `budget` tokens: summarize the old turns, keep recent ones verbatim.

    `messages` starts with a user message and ends with the newest user message.
    Size of a list = sum(count(m.text) for m in messages). Never modify the input list.

    1. If it already fits the budget, return a copy, and do not call summarize.
    2. Otherwise split it: `recent` = the last `keep_last` messages, extended by one message
       to the left if it would start with an assistant message (it must start with a user
       message); `old` = everything before it.
    3. summary = summarize(old)   (called with the old messages, in order)
    4. Return [merged] + recent[1:], where merged is a user message with the text
           "<conversation_summary>\\n" + summary + "\\n</conversation_summary>\\n\\n" + recent[0].text
       (putting the summary into the first kept user message keeps user/assistant alternation).
    5. If the result is still over budget, try again with keep_last reduced by 2 (never below 1),
       summarizing more of the conversation. When keep_last is 1, return the result even if it
       does not fit: the caller decides what to do.
    An earlier summary is just part of `old` the next time, so compacting again merges it.
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement compact")
