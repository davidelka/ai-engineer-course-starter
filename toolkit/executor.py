"""Running the tool calls a model asked for. The model never runs anything: it emits a
structured REQUEST, and this module decides whether and how to run it.

execute_tool() is the reference for lesson 14, exercise 3 (mine.py). One call in,
one ToolResult out, and it NEVER raises: every failure becomes an is_error result
whose text tells the model what went wrong and what to do next.

    unknown tool name        -> is_error, lists the available tools
    arguments not JSON       -> is_error (ToolCall.parse_error)
    arguments fail Pydantic  -> is_error, one line per problem (field, message, value)
    side effect, no consent  -> is_error "NOT executed: waiting for human confirmation"
    tool raises ToolError    -> is_error with the tool's own message (written for the model)
    tool raises anything else-> is_error "internal error" (type only; details go to YOUR log)
    tool takes too long      -> is_error "timed out after N s"
    success                  -> JSON text, cut to max_chars
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import BaseModel, ValidationError

from llmkit.structured import format_errors
from llmkit.types import ToolCall, ToolResult

from .registry import Registry, ToolError

log = logging.getLogger("toolkit")
DEFAULT_TIMEOUT_S = 5.0
MAX_CHARS = 8000
# One shared pool: a timed-out call keeps its thread until the function returns (Python
# cannot kill a thread). Tools that may hang for real belong in a subprocess or behind
# their own client timeouts; this timeout protects the LOOP, not the machine.
_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tool")


def to_text(value: Any, max_chars: int = MAX_CHARS) -> str:
    """Tool output -> the text the model will read. Long outputs are cut with a note,
    because every character is input tokens on this call AND every later call."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if len(text) > max_chars:
        text = text[:max_chars] + f"... [truncated: {len(text) - max_chars} more characters]"
    return text


def execute_tool(call: ToolCall, registry: Registry, *, timeout_s: Optional[float] = None,
                 confirmed: Optional[Callable[[ToolCall], bool]] = None, max_chars: int = MAX_CHARS) -> ToolResult:
    """Validate, authorize, run with a timeout, and package ONE tool call. Never raises.

    confirmed(call) -> bool is asked for side-effect tools; None means "no human has
    approved anything", so side-effect tools are never run.
    """
    def err(msg: str) -> ToolResult:
        return ToolResult(call.id, msg, is_error=True, name=call.name)

    spec = registry.get(call.name)
    if spec is None:
        return err(f"Unknown tool {call.name!r}. Available tools: {', '.join(registry.names())}.")
    if call.parse_error:
        return err(f"Invalid arguments for {call.name}: {call.parse_error}. Send a JSON object.")
    try:
        args = spec.input_model.model_validate(call.arguments)
    except ValidationError as exc:
        return err(f"Invalid arguments for {call.name}:\n{format_errors(exc)}\nFix them and call the tool again.")
    if spec.side_effect and not (confirmed and confirmed(call)):
        return err(f"NOT executed: {call.name} changes data and needs a human confirmation first. "
                   "Tell the user exactly what will be done and ask them to confirm.")
    limit = spec.timeout_s or timeout_s or DEFAULT_TIMEOUT_S
    t0 = time.perf_counter()
    future = _POOL.submit(spec.fn, args)
    try:
        value = future.result(timeout=limit)
    except FutureTimeout:
        future.cancel()
        return err(f"{call.name} timed out after {limit:g}s. The system may be slow: try again once, "
                   "or tell the user it is unavailable.")
    except ToolError as exc:
        return err(str(exc))
    except Exception as exc:  # noqa: BLE001 - the loop must survive any tool bug
        log.error("tool %s crashed: %s", call.name, traceback.format_exc())
        return err(f"{call.name} failed with an internal error ({type(exc).__name__}). "
                   "This is not caused by your arguments; do not retry more than once.")
    log.debug("tool %s ok in %.3fs", call.name, time.perf_counter() - t0)
    return ToolResult(call.id, to_text(value, max_chars), name=call.name)


@dataclass
class TraceEntry:
    round: int
    call_id: str
    name: str
    arguments: dict
    is_error: bool
    result: str
    ms: float


@dataclass
class Executor:
    """execute_tool plus: parallel execution of read-only calls, a trace, and a
    confirmation hook. Results come back in the SAME ORDER as the calls."""

    registry: Registry
    timeout_s: float = DEFAULT_TIMEOUT_S
    confirmed: Optional[Callable[[ToolCall], bool]] = None
    max_chars: int = MAX_CHARS
    run: Callable[..., ToolResult] = execute_tool  # swap in mine.execute_tool for the lab
    trace: list[TraceEntry] = field(default_factory=list)
    round: int = 0

    def __call__(self, calls: list[ToolCall]) -> list[ToolResult]:
        return self.execute_all(calls)

    def _one(self, call: ToolCall) -> ToolResult:
        t0 = time.perf_counter()
        kw = {"timeout_s": self.timeout_s}
        if self.run is execute_tool:
            kw.update(confirmed=self.confirmed, max_chars=self.max_chars)
        r = self.run(call, self.registry, **kw)
        self.trace.append(TraceEntry(self.round, call.id, call.name, call.arguments, r.is_error,
                                     r.text[:300], (time.perf_counter() - t0) * 1000))
        return r

    def execute_all(self, calls: list[ToolCall]) -> list[ToolResult]:
        """Read-only calls run concurrently; side-effect calls run one at a time, in order,
        after them (ordering and shared state matter for writes)."""
        self.round += 1
        results: dict[int, ToolResult] = {}
        reads = [(i, c) for i, c in enumerate(calls) if not getattr(self.registry.get(c.name), "side_effect", False)]
        writes = [(i, c) for i, c in enumerate(calls) if (i, c) not in reads]
        if len(reads) > 1:
            with ThreadPoolExecutor(max_workers=min(8, len(reads))) as pool:
                for (i, _), r in zip(reads, pool.map(lambda ic: self._one(ic[1]), reads)):
                    results[i] = r
        else:
            for i, c in reads:
                results[i] = self._one(c)
        for i, c in writes:
            results[i] = self._one(c)
        return [results[i] for i in range(len(calls))]
