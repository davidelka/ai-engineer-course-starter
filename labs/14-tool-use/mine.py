"""Your code for lesson 14. Each part is checked by tests in ./tests.

Reference versions live in toolkit/ (executor.py, loop.py, confirm.py).
Try not to peek before your tests pass.

    python -m pytest -q labs/14-tool-use/tests
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

    Every result has call_id=call.id and name=call.name. In order:
      1. registry.get(call.name) is None
           -> is_error, text contains "Unknown tool" and the available names (registry.names()).
      2. call.parse_error is set (the arguments were not valid JSON)
           -> is_error, text contains "Invalid arguments" and the parse error.
      3. spec.input_model.model_validate(call.arguments) raises ValidationError
           -> is_error, text contains "Invalid arguments for <name>" and format_errors(exc)
              (so the model sees each field, message and value, and can fix the call).
      4. spec.side_effect is True and not (confirmed and confirmed(call))
           -> is_error, text starts with "NOT executed". The function must NOT be called.
      5. Run spec.fn(validated_args) with a timeout: spec.timeout_s if set, else timeout_s.
         Use a ThreadPoolExecutor and future.result(timeout=...).
           timeout          -> is_error, text contains "timed out"
           ToolError e      -> is_error, text == str(e)   (the tool wrote it for the model)
           other Exception  -> is_error, text contains "internal error" and the exception TYPE
                               name, but NOT the message or traceback (they may hold secrets)
      6. Success -> is_error False, text = to_text(value) (JSON, truncated if huge).
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement execute_tool")


# ------------------------------------------------------------------ exercise 4
def run_tool_loop(llm: LLM, question: str, registry: Registry, *, system: str = SYSTEM, max_rounds: int = 5,
                  executor: Optional[Callable[[list[ToolCall]], list[ToolResult]]] = None) -> LoopResult:
    """Answer ONE question with tools. Returns toolkit.loop.LoopResult.

    req = ChatRequest(messages=[Message("user", question)], system=system, tools=registry.tools())
    run = executor or (lambda calls: [execute_tool(c, registry) for c in calls])
    Loop:
      r = llm.complete(req); count model_calls, input/output tokens and cost_usd (r.cost_usd or 0)
      - no r.tool_calls  -> append r.message, text = r.text, stop = "answer", done
      - rounds == max_rounds already -> stop = "max_rounds", text says it stopped; do NOT append
        the unanswered tool calls (a history ending in tool calls without results is invalid)
      - otherwise: rounds += 1; record the calls; append r.message (the assistant turn AS
        RECEIVED: it carries raw provider data such as Gemini thought signatures);
        results = run(r.tool_calls); record them;
        append Message.with_tool_results(results)   <- ALL results in ONE user message
    Set result.messages = the whole conversation at the end.
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement run_tool_loop")


# ------------------------------------------------------------------ exercise 6
def call_fingerprint(call: ToolCall) -> str:
    """sha256 hex of json.dumps({"name": call.name, "arguments": call.arguments},
    sort_keys=True, separators=(",", ":"), ensure_ascii=False). The same call with keys in
    another order gives the same fingerprint; any change in a value gives a different one."""
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement call_fingerprint")


@dataclass
class ConfirmationGate:
    """Human approval for side-effect tools. The model can ASK to run a tool; only your app,
    after a human said yes, can APPROVE it, and the model never sees the token.

    approve(call) -> token: secrets.token_urlsafe(24), stored with call_fingerprint(call) and
        an expiry of clock() + ttl_s. Also remember call.id -> token (for confirmed()).
    check(call, token) -> bool: True only if the token is known, not expired, and was issued
        for this call's fingerprint. A presented token is consumed either way (single use).
        Compare fingerprints with hmac.compare_digest.
    confirmed(call) -> bool: the Executor hook. Looks up the token remembered for call.id
        (pop it) and returns check(call, token). No approval -> False.
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
