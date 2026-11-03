"""Raw JSON-RPC over stdio, with no SDK on the client side (lesson 17, exercise 1).

The stdio transport is just newline-delimited JSON-RPC: the client launches the server as a
subprocess, writes one JSON object per line to its stdin, and reads one JSON object per line
from its stdout. The server's stderr is for logs (anything else on stdout breaks the stream).

    with RawStdio([sys.executable, "-m", "mcpkit"]) as rs:
        rs.request("initialize", {...})          # prints >> and << with the exact JSON
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Optional

MODERN = "2026-07-28"
LEGACY = "2025-11-25"


def modern_meta(capabilities: Optional[dict] = None, client: str = "raw-stdio") -> dict:
    """The per-request envelope every 2026-07-28 request carries in params._meta."""
    return {"io.modelcontextprotocol/protocolVersion": MODERN,
            "io.modelcontextprotocol/clientCapabilities": capabilities or {},
            "io.modelcontextprotocol/clientInfo": {"name": client, "version": "17.0"}}


def shorten(obj: Any, limit: int = 220) -> Any:
    """Cut long strings (descriptions, document text) so a trace stays readable."""
    if isinstance(obj, str):
        return obj if len(obj) <= limit else obj[:limit] + f"... [{len(obj) - limit} more chars]"
    if isinstance(obj, list):
        return [shorten(x, limit) for x in obj]
    if isinstance(obj, dict):
        return {k: shorten(v, limit) for k, v in obj.items()}
    return obj


class RawStdio:
    def __init__(self, argv: list[str], *, show: bool = True, limit: int = 220, max_items: int = 3, out=sys.stdout,
                 cwd: Optional[str] = None):
        self.argv, self.show, self.limit, self.max_items, self.out, self.cwd = argv, show, limit, max_items, out, cwd
        self.next_id = 1
        self.proc: Optional[subprocess.Popen] = None

    def __enter__(self) -> "RawStdio":
        self.proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
                                     cwd=self.cwd)
        return self

    def __exit__(self, *exc) -> None:
        if self.proc:
            self.proc.stdin.close()  # EOF on stdin is how a stdio client ends the session
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def _print(self, arrow: str, msg: dict) -> None:
        if not self.show:
            return
        m = shorten(msg, self.limit)
        res = m.get("result") if isinstance(m.get("result"), dict) else None
        if res:  # long lists (tools, resources): keep the first few
            for key in ("tools", "resources", "prompts", "resourceTemplates"):
                if isinstance(res.get(key), list) and len(res[key]) > self.max_items:
                    n = len(res[key])
                    res[key] = res[key][: self.max_items] + [f"... {n - self.max_items} more"]
        print(f"{arrow} {json.dumps(m, ensure_ascii=False, indent=2)}", file=self.out)

    def send(self, msg: dict) -> None:
        self._print(">>", msg)
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def notify(self, method: str, params: Optional[dict] = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self.send(msg)

    def request(self, method: str, params: Optional[dict] = None) -> dict:
        rid = self.next_id
        self.next_id += 1
        msg = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            msg["params"] = params
        self.send(msg)
        while True:  # notifications (progress, logs) may arrive before the response
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("server closed stdout (crashed?) - run it directly to see its stderr")
            reply = json.loads(line)
            self._print("<<", reply)
            if reply.get("id") == rid:
                return reply
