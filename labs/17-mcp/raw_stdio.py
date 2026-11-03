"""Exercise 1: speak MCP by hand. Launch acme-mcp over stdio and print every JSON-RPC message.

    python labs/17-mcp/raw_stdio.py --era legacy     # 2025-11-25: initialize handshake, then requests
    python labs/17-mcp/raw_stdio.py --era modern     # 2026-07-28: no handshake, _meta on every request,
                                                     #   and a multi round-trip elicitation
    python labs/17-mcp/raw_stdio.py --era mixed      # what the server does when the eras are mixed

No MCP SDK on this side: just subprocess, json and newlines (mcpkit/wire.py).
"""

import argparse
import sys
import tempfile
from pathlib import Path

import _lab  # noqa: F401  (paths)
from mcpkit.wire import LEGACY, RawStdio, modern_meta

p = argparse.ArgumentParser()
p.add_argument("--era", choices=["legacy", "modern", "mixed"], default="legacy")
p.add_argument("--approve", action="store_true", help="modern era: answer yes to the confirmation (writes to a temp db)")
p.add_argument("--full", action="store_true", help="do not shorten long strings")
a = p.parse_args()
db = Path(tempfile.mkdtemp()) / "requests.db"
server = [sys.executable, "-m", "mcpkit", "--requests-db", str(db)]


def title(t):
    print(f"\n{'=' * 8} {t} {'=' * 8}")


with RawStdio(server, limit=10_000 if a.full else 220) as rs:
    if a.era == "legacy":
        title("1. initialize: the client proposes a version and declares its capabilities")
        rs.request("initialize", {"protocolVersion": LEGACY, "capabilities": {},
                                  "clientInfo": {"name": "raw-stdio", "version": "17.0"}})
        title("2. notifications/initialized: a notification (no id, no reply)")
        rs.notify("notifications/initialized")
        title("3. tools/list")
        rs.request("tools/list")
        title("4. tools/call")
        rs.request("tools/call", {"name": "get_oncall_for_service", "arguments": {"service": "flow-api"}})
        title("5. tools/call with a bad argument: an error RESULT (isError), not a JSON-RPC error")
        rs.request("tools/call", {"name": "get_system_info", "arguments": {"system": "salesforc"}})
        title("6. a method that does not exist: a JSON-RPC error")
        rs.request("tools/run", {"name": "x"})
        title("7. resources/read and prompts/get")
        rs.request("resources/read", {"uri": "acme://docs/eng-service-catalog"})
        rs.request("prompts/get", {"name": "triage-access-request",
                                   "arguments": {"employee": "dana.levi@acme.example", "system": "figma"}})
    elif a.era == "modern":
        caps = {"elicitation": {"form": {}}}
        title("1. server/discover (optional): versions, capabilities, identity")
        rs.request("server/discover", {"_meta": modern_meta(caps)})
        title("2. tools/list: no handshake happened, so the envelope is in _meta")
        rs.request("tools/list", {"_meta": modern_meta(caps)})
        title("3. tools/call")
        rs.request("tools/call", {"name": "get_oncall_for_service", "arguments": {"service": "flow-api"},
                                  "_meta": modern_meta(caps)})
        title("4. a side effect: the server needs the human, so it answers input_required")
        args = {"employee": "dana.levi@acme.example", "system": "figma", "access_level": "editor",
                "justification": "design reviews for the Q1 launch", "idempotency_key": "dana:figma:editor"}
        first = rs.request("tools/call", {"name": "create_access_request", "arguments": args, "_meta": modern_meta(caps)})
        res = first.get("result", {})
        if res.get("resultType") == "input_required":
            [(key, req)] = res["inputRequests"].items()
            print(f"\n   The HOST would now show the human: {req['params']['message']}")
            answer = {"action": "accept", "content": {"approve": True}} if a.approve else {"action": "decline"}
            title(f"5. retry the SAME request with inputResponses ({answer['action']}) and requestState")
            rs.request("tools/call", {"name": "create_access_request", "arguments": args,
                                      "inputResponses": {key: answer}, "requestState": res["requestState"],
                                      "_meta": modern_meta(caps)})
        title("6. the same call from a client WITHOUT the elicitation capability")
        rs.request("tools/call", {"name": "create_access_request", "arguments": args, "_meta": modern_meta({})})
    else:
        title("A modern request first decides the connection's era ...")
        rs.request("tools/list", {"_meta": modern_meta()})
        title("... so a later initialize is refused (UnsupportedProtocolVersion)")
        rs.request("initialize", {"protocolVersion": LEGACY, "capabilities": {},
                                  "clientInfo": {"name": "raw-stdio", "version": "17.0"}})
