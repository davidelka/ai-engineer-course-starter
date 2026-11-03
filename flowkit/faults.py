"""Failure injection for the workflow's tools (lesson 16, exercise 7).

    reg = with_faults(acme_registry(...), {"get_system_info": ("timeout", 2)}, delay_s=0.6, timeout_s=0.2)

The first 2 calls of get_system_info sleep longer than the tool timeout, so execute_tool
returns "timed out", the node raises ToolUnavailable, and the node's RetryPolicy retries.
Kinds:
  timeout   sleep delay_s (> timeout_s) on the first N calls
  error     raise RuntimeError on the first N calls (a bug: NOT retried, becomes ToolError)
A spec of "timeout:get_system_info:2" (the CLI form) is parsed by parse_fault.
"""

from __future__ import annotations

import threading
import time
from dataclasses import replace

from toolkit.registry import Registry


def parse_fault(spec: str) -> dict[str, tuple[str, int]]:
    """'timeout:get_system_info:2,error:check_policy:1' -> {name: (kind, n)}"""
    out = {}
    for part in filter(None, (spec or "").split(",")):
        kind, name, n = part.split(":")
        if kind not in ("timeout", "error"):
            raise ValueError(f"fault kind must be timeout or error, got {kind!r}")
        out[name] = (kind, int(n))
    return out


def with_faults(registry: Registry, faults: dict[str, tuple[str, int]], *, delay_s: float = 0.6,
                timeout_s: float = 0.2) -> Registry:
    """A copy of the registry whose named tools fail their first N calls."""
    counts = {name: 0 for name in faults}
    lock = threading.Lock()
    out = Registry()
    for name, spec in registry.specs.items():
        if name not in faults:
            out.register(spec)
            continue
        kind, n = faults[name]

        def wrapped(args, _fn=spec.fn, _name=name, _kind=kind, _n=n):
            with lock:
                counts[_name] += 1
                k = counts[_name]
            if k <= _n:
                if _kind == "timeout":
                    time.sleep(delay_s)
                else:
                    raise RuntimeError(f"injected failure #{k}")
            return _fn(args)

        out.register(replace(spec, fn=wrapped, timeout_s=timeout_s))
    out.fault_counts = counts  # type: ignore[attr-defined]
    return out
