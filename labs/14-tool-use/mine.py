"""Your code for lesson 14. Each part is checked by tests in ./tests.

Reference versions live in toolkit/ (executor.py, loop.py, confirm.py).
Try not to peek before your tests pass.

    python -m pytest -q labs/14-tool-use/tests

Each docstring is a contract: what goes in, what comes out, and the rules the result must follow.
When you are stuck, HINTS.md has graded hints for every function (direction, structure, full algorithm).
"""

from __future__ import annotations

import hashlib  # noqa: F401  (exercise 6)
import json  # noqa: F401
import secrets  # noqa: F401  (exercise 6)
import time  # noqa: F401
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout  # noqa: F401
from dataclasses import dataclass, field  # noqa: F401
from typing import Callable, Optional

from pydantic import ValidationError  # noqa: F401

from llmkit import LLM
from llmkit.structured import format_errors  # noqa: F401  (lesson 3: one line per validation error)
from llmkit.types import ChatRequest, Message, ToolCall, ToolResult  # noqa: F401
from toolkit.executor import to_text  # noqa: F401  (output -> JSON text, cut to max_chars)
from toolkit.loop import SYSTEM, LoopResult  # noqa: F401
from toolkit.registry import Registry, ToolError  # noqa: F401


# ------------------------------------------------------------------ exercise 3
def execute_tool(call: ToolCall, registry: Registry, *, timeout_s: float = 5.0,
                 confirmed: Optional[Callable[[ToolCall], bool]] = None) -> ToolResult:
    """Run ONE tool call safely and return a ToolResult. NEVER raise.

    Every result has call_id=call.id and name=call.name. Errors are is_error results whose text
    the model can act on, and each case must be recognizable by these words in the text:
      - unknown tool: "Unknown tool", plus the available names (registry.names());
      - arguments that were not valid JSON (call.parse_error): "Invalid arguments" and the parse error;
      - arguments that fail spec.input_model: "Invalid arguments for <name>" and format_errors(exc);
      - a side-effect tool (spec.side_effect) that `confirmed` did not approve: text starts with
        "NOT executed", and the tool function is never called;
      - the tool ran longer than spec.timeout_s (if set) or timeout_s: "timed out";
      - the tool raised ToolError e: text == str(e) exactly (the tool wrote it for the model);
      - any other exception: "internal error" and the exception TYPE name only, never its message
        or traceback (they may hold secrets).
    Success: is_error False, text = to_text(value).

    Stuck? HINTS.md -> execute_tool
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement execute_tool")


# ------------------------------------------------------------------ exercise 4
def run_tool_loop(llm: LLM, question: str, registry: Registry, *, system: str = SYSTEM, max_rounds: int = 5,
                  executor: Optional[Callable[[list[ToolCall]], list[ToolResult]]] = None) -> LoopResult:
    """Answer ONE question with tools. Returns toolkit.loop.LoopResult (read its fields).

    The model sees the question (one user message), `system`, and registry.tools(). Tool calls are
    run by `executor` if given, else by execute_tool on each call. The loop ends with:
      - stop "answer": a reply without tool calls; text = its text;
      - stop "max_rounds": the model still wants tools after max_rounds rounds of tool calls;
        text says it stopped. The history must stay valid: it never ends with tool calls that
        have no results.
    The result counts model_calls, rounds, input/output tokens and cost_usd (a missing cost is 0),
    records every call and result, and has messages = the whole conversation. Assistant turns go
    into the history exactly as received (they carry raw provider data such as Gemini thought
    signatures), and all the results of one round go back in ONE user message.

    Stuck? HINTS.md -> run_tool_loop
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement run_tool_loop")


# ------------------------------------------------------------------ exercise 6
def call_fingerprint(call: ToolCall) -> str:
    """A stable sha256 hex digest (64 characters) of the call's name and arguments.

    The same call with its argument keys in another order gives the same fingerprint; any change
    in the name or a value gives a different one. Non-ASCII text (Hebrew) must be supported.

    Stuck? HINTS.md -> call_fingerprint
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement call_fingerprint")


@dataclass
class ConfirmationGate:
    """Human approval for side-effect tools. The model can ASK to run a tool; only your app,
    after a human said yes, can APPROVE it, and the model never sees the token.

    approve(call) -> token: an unguessable string (at least 24 characters, unique per call), valid
        for ttl_s seconds as measured by clock(), and bound to this exact call (name + arguments).
    check(call, token) -> bool: True only for a known, unexpired token issued for this same call
        (see call_fingerprint). A presented token is consumed either way: single use. None or an
        unknown token -> False. Compare secrets in constant time.
    confirmed(call) -> bool: the Executor hook (execute_tool's `confirmed`). True only if a token
        was approved for this call.id and it passes check; the approval is used up. No approval -> False.

    Stuck? HINTS.md -> ConfirmationGate
    """

    ttl_s: float = 300.0
    clock: Callable[[], float] = time.monotonic

    # TODO(ex6): add the storage you need (field(default_factory=dict)) and the three methods.
    def approve(self, call: ToolCall) -> str:
        raise NotImplementedError("exercise 6: implement ConfirmationGate.approve")

    def check(self, call: ToolCall, token: Optional[str]) -> bool:
        raise NotImplementedError("exercise 6: implement ConfirmationGate.check")

    def confirmed(self, call: ToolCall) -> bool:
        raise NotImplementedError("exercise 6: implement ConfirmationGate.confirmed")
