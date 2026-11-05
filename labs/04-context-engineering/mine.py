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

    `body` is the JSON you would POST to /v1/messages: optional "tools" (list of dicts),
    optional "system" (a string or a list of {"type": "text", "text": ...} blocks),
    "messages" (each content a string or a list of blocks), optional top-level
    "cache_control". `count(text) -> int` counts tokens (tests pass a word counter).

    Returns exactly five Layer objects named as in LAYERS, in that order, even when empty:
      tools      each tool as json.dumps(tool, ensure_ascii=False), its "cache_control" key left out
      system     the system prompt text
      history    every message except the last one
      retrieved  the <documents>...</documents> spans (tags included) in the LAST message
      user_turn  the rest of the last message, without those spans
    Each piece is counted separately and summed: count(a) + count(b), not count(a + b).

    Layer.cached_tokens: how many of the layer's tokens lie in the cached prefix, that is,
    from the start of the request (order tools -> system -> messages) up to and including
    the last block that has "cache_control". A top-level "cache_control" makes everything
    cached; no breakpoint at all makes every cached_tokens 0.

    Stuck? HINTS.md -> layer_report
    """
    # TODO(ex1)
    raise NotImplementedError("exercise 1: implement layer_report")


# ------------------------------------------------------------------ exercise 2
def build_hr_request(policies: str, question: str, *, employee: str, today: str,
                     history: Optional[list[Message]] = None, ttl: str = "5m") -> ChatRequest:
    """The lesson-1 HR assistant, rebuilt so its big stable part is cached.

    naive_hr_request() (ctxkit/layout.py) is the "before": the date and the employee are at
    the top of its system prompt and the documents come after the question, so nothing caches.

    Returns a ChatRequest with max_tokens=400 where:
      - system is a list of exactly two Blocks: HR_INSTRUCTIONS, then the policies as
        "<documents>\n" + policies.strip() + "\n</documents>";
      - the only cache breakpoint is on the last system block, with cache=ttl;
      - the system is IDENTICAL for any question, employee or date;
      - messages = history (unchanged, may be None) + one new user message, a plain string,
        with the dynamic context first and the question last, ending exactly with
        "<question>\n" + question + "\n</question>". The context block is
            <context>
            employee: <employee>
            today: <today>
            </context>

    Stuck? HINTS.md -> build_hr_request
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement build_hr_request")


# ------------------------------------------------------------------ exercise 6
def compact(messages: list[Message], budget: int, count: Callable[[str], int],
            summarize: Callable[[list[Message]], str], keep_last: int = 4) -> list[Message]:
    """Fit a conversation into `budget` tokens: summarize old turns, keep recent ones verbatim.

    `messages` starts with a user message and ends with the newest user message.
    Size of a list = sum(count(m.text) for m in messages). Never modify the input list.

    Returns a new list:
      - if it already fits: a copy, and summarize is not called;
      - otherwise: a user message with the text
            "<conversation_summary>\n" + summary + "\n</conversation_summary>\n\n" + <first kept message text>
        followed by the other kept messages verbatim. The kept part is the last `keep_last`
        messages, plus one more if needed so that it starts with a user message;
        summary = summarize(<all messages before the kept part>, in order).
      - if that is still over budget, keep fewer messages and summarize more; with a single
        kept message, return the result even if it does not fit.
    Compacting an already compacted conversation must work (the old summary gets summarized).

    Stuck? HINTS.md -> compact
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement compact")
