"""Exercise 6 (demo): a side-effect tool behind a human confirmation, and idempotency.

    python labs/14-tool-use/confirm_demo.py                     # mock model, your ConfirmationGate (mine.py)
    python labs/14-tool-use/confirm_demo.py --reference         # toolkit's gate
    python labs/14-tool-use/confirm_demo.py --model anthropic:claude-haiku-5-5
    python labs/14-tool-use/confirm_demo.py --yes                # approve without asking (for scripts)

Flow: the model asks for create_access_request -> the executor refuses ("NOT executed")
-> YOUR app shows the human exactly what will happen -> yes issues a token bound to that
exact call -> the call runs once. Then the same call is replayed to show that the
idempotency_key prevents a duplicate record.
"""

from __future__ import annotations

import argparse
import json
import sqlite3

import _lab  # noqa: F401
from _lab import DEFAULT_MODEL, make_llm, requests_db
from llmkit.types import ChatRequest, Message
from toolkit import Executor, acme_registry
from toolkit.loop import SYSTEM

QUESTION = ("Please file an access request: dana.levi@acme.example needs a Figma editor seat for the Q4 design "
            "review. Use idempotency key dana.levi@acme.example:figma:editor.")
RULES = [{"match": "file an access request", "calls": [{"name": "create_access_request", "arguments": {
    "employee": "dana.levi@acme.example", "system": "figma", "access_level": "editor",
    "justification": "Q4 design review", "duration_days": None,
    "idempotency_key": "dana.levi@acme.example:figma:editor"}}]}]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mock", help=f"'mock' or e.g. {DEFAULT_MODEL}")
    ap.add_argument("--reference", action="store_true", help="use toolkit.ConfirmationGate instead of mine.py")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.reference:
        from toolkit import ConfirmationGate
    else:
        from mine import ConfirmationGate
    gate = ConfirmationGate()
    reg = acme_registry(requests_db=requests_db())
    ex = Executor(reg, confirmed=gate.confirmed)
    llm = make_llm(a.model, {"tool_script": json.dumps(RULES)})
    req = ChatRequest(messages=[Message("user", QUESTION)], system=SYSTEM, tools=reg.tools(), max_tokens=800)

    for rnd in range(1, 6):
        r = llm.complete(req)
        if not r.tool_calls:
            print(f"\nFINAL ANSWER:\n{r.text}")
            break
        req.messages.append(r.message)
        for c in r.tool_calls:
            print(f"\n[round {rnd}] model asks: {c.name}({json.dumps(c.arguments, ensure_ascii=False)})")
            spec = reg.get(c.name)
            if spec and spec.side_effect:
                print("  " + f"The assistant wants to run {c.name} with the arguments above.")
                yes = a.yes or input("  Approve? [y/N] ").strip().lower() == "y"
                if yes:
                    gate.approve(c)  # the token stays on OUR side; the model never sees it
                    print("  approved by a human: token issued for this exact call")
        results = ex(r.tool_calls)
        for res in results:
            print(f"  -> is_error={res.is_error}: {res.text[:240]}")
        req.messages.append(Message.with_tool_results(results))

    # Replay: the same call again, as a retry after a network error would do.
    last = next((m for m in reversed(req.messages) if m.role == "assistant" and m.tool_calls), None)
    if last:
        c = last.tool_calls[0]
        gate.approve(c)
        again = ex([c])[0]
        print(f"\nReplaying the same call (as a retry would): {again.text[:200]}")
    con = sqlite3.connect(requests_db())
    try:
        rows = con.execute("SELECT id, employee_id, system, access_level, route, status, approver FROM access_requests").fetchall()
    except sqlite3.OperationalError:
        rows = []
    print(f"\nrequests table ({requests_db()}): {len(rows)} rows")
    for row in rows[-5:]:
        print("  ", row)


if __name__ == "__main__":
    main()
