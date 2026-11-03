"""Human confirmation for side-effect tools (reference for lesson 14, exercise 6).

The model can ask to run create_access_request, but it cannot APPROVE it: approval
is a token that only your application issues, after a human saw exactly what will
happen. The token is bound to the exact call (tool name + canonical arguments), is
single-use, expires, and is never shown to the model, so text in a document (prompt
injection) cannot produce one.

    gate = ConfirmationGate()
    pending = gate.request(call)              # -> summary to show the human
    token = gate.approve(call)                 # the human said yes (in YOUR UI)
    gate.check(call, token)                    # True once; False for other args, reuse, or expiry
    executor = Executor(registry, confirmed=gate.confirmed)   # run approved calls only
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from llmkit.types import ToolCall


def call_fingerprint(call: ToolCall) -> str:
    """sha256 of the tool name and the arguments in canonical JSON (sorted keys), so
    the same request always has the same fingerprint and any change in arguments
    gives a different one."""
    canon = json.dumps({"name": call.name, "arguments": call.arguments}, sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode()).hexdigest()


@dataclass
class ConfirmationGate:
    ttl_s: float = 300.0
    clock: Callable[[], float] = time.monotonic
    _issued: dict[str, tuple[str, float]] = field(default_factory=dict)  # token -> (fingerprint, expires_at)
    _approved: dict[str, str] = field(default_factory=dict)  # call id -> token (for confirmed())

    def request(self, call: ToolCall) -> str:
        """A human-readable summary of exactly what would be done."""
        args = ", ".join(f"{k}={v!r}" for k, v in sorted(call.arguments.items()))
        return f"The assistant wants to run {call.name}({args}). Approve? [y/N]"

    def approve(self, call: ToolCall) -> str:
        """Issue a single-use token bound to this exact call."""
        token = secrets.token_urlsafe(24)
        self._issued[token] = (call_fingerprint(call), self.clock() + self.ttl_s)
        self._approved[call.id] = token
        return token

    def check(self, call: ToolCall, token: Optional[str]) -> bool:
        """True only for a known, unexpired, unused token issued for THIS call's
        fingerprint. Consumes the token (single use) whenever it is presented."""
        if not token or token not in self._issued:
            return False
        fp, expires = self._issued.pop(token)
        return self.clock() <= expires and hmac.compare_digest(fp, call_fingerprint(call))

    def confirmed(self, call: ToolCall) -> bool:
        """Hook for Executor(confirmed=...): was THIS call approved by a human?"""
        return self.check(call, self._approved.pop(call.id, None))
