"""Exercise 6: human confirmation tokens for side-effect tools."""
import json

import mine
from llmkit.types import ToolCall
from toolkit import Executor

A = ToolCall("1", "create_access_request", {"employee": "E016", "system": "figma", "access_level": "editor"})
B = ToolCall("2", "create_access_request", {"employee": "E016", "system": "figma", "access_level": "admin"})


def test_fingerprint_is_canonical():
    same = ToolCall("9", A.name, dict(reversed(list(A.arguments.items()))))
    assert mine.call_fingerprint(A) == mine.call_fingerprint(same)
    assert mine.call_fingerprint(A) != mine.call_fingerprint(B)
    assert len(mine.call_fingerprint(A)) == 64


def test_token_is_bound_and_single_use():
    gate = mine.ConfirmationGate()
    t = gate.approve(A)
    assert isinstance(t, str) and len(t) >= 24
    assert gate.check(A, t) and not gate.check(A, t)  # single use
    t2 = gate.approve(A)
    assert not gate.check(B, t2)  # other arguments
    assert not gate.check(A, t2)  # consumed by the failed attempt
    assert not gate.check(A, None) and not gate.check(A, "guess")


def test_tokens_expire():
    now = [100.0]
    gate = mine.ConfirmationGate(ttl_s=10, clock=lambda: now[0])
    t = gate.approve(A)
    now[0] = 111.0
    assert not gate.check(A, t)


def test_tokens_are_unique():
    gate = mine.ConfirmationGate()
    assert len({gate.approve(A) for _ in range(50)}) == 50


def test_executor_hook(reg):
    gate = mine.ConfirmationGate()
    call = ToolCall("c1", "create_access_request", {"employee": "dana.levi@acme.example", "system": "figma",
                                                   "access_level": "editor", "justification": "review",
                                                   "duration_days": None, "idempotency_key": "dana:figma:editor"})
    ex = Executor(reg, confirmed=gate.confirmed)
    assert ex([call])[0].text.startswith("NOT executed")  # nobody approved
    gate.approve(call)
    res = json.loads(ex([call])[0].text)
    assert res["status"] == "pending_manager" and res["approver"] == "E005"
    assert ex([call])[0].is_error  # approval was used up
    gate.approve(call)
    assert json.loads(ex([call])[0].text)["deduplicated"] is True  # idempotency key: no second record
