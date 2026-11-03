"""Exercise 6: acme-mcp over Streamable HTTP, protected by a bearer token.

    python labs/17-mcp/http_demo.py              # starts the server itself with two fresh tokens, runs 5 checks
    python labs/17-mcp/http_demo.py --port 8799

What it shows, in order:
  1. no token          -> 401 + WWW-Authenticate: Bearer ... resource_metadata="..."
  2. the metadata URL  -> RFC 9728 Protected Resource Metadata (who issues tokens, which scopes)
  3. wrong token       -> 401 (invalid_token)
  4. read-only token   -> tools work; create_access_request refused for the missing acme:write scope
  5. full token        -> create_access_request asks for confirmation (elicitation) and files the request
Tokens are generated here and passed to the server in its ENVIRONMENT; only a short prefix is printed.
"""

import argparse
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import _lab
import httpx

from llmkit.types import ToolCall
from mcpkit.bridge import HttpTarget, MCPToolbox, scripted_elicitation

p = argparse.ArgumentParser()
p.add_argument("--port", type=int, default=8765)
a = p.parse_args()
url = f"http://127.0.0.1:{a.port}/mcp"
full, read = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
db = Path(tempfile.mkdtemp()) / "requests.db"
env = {**os.environ, "ACME_MCP_TOKEN": full, "ACME_MCP_TOKEN_READ": read, "PYTHONPATH": str(_lab.ROOT)}
proc = subprocess.Popen([sys.executable, "-m", "mcpkit", "--transport", "http", "--auth", "--port", str(a.port),
                         "--requests-db", str(db)], env=env, cwd=_lab.ROOT, stderr=subprocess.DEVNULL)
print(f"server: {url}  full token {full[:6]}…  read-only token {read[:6]}…")
ARGS = {"employee": "dana.levi@acme.example", "system": "figma", "access_level": "editor",
        "justification": "design reviews", "idempotency_key": "http-demo:dana:figma:editor"}
try:
    for _ in range(50):  # wait for uvicorn
        try:
            httpx.get(f"http://127.0.0.1:{a.port}/.well-known/oauth-protected-resource/mcp", timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    hdr = {"accept": "application/json, text/event-stream", "content-type": "application/json"}

    print("\n1. POST /mcp without a token")
    r = httpx.post(url, json=body, headers=hdr)
    print(f"   HTTP {r.status_code}\n   WWW-Authenticate: {r.headers.get('www-authenticate')}")

    print("\n2. GET the resource_metadata URL from that header")
    meta_url = r.headers["www-authenticate"].split('resource_metadata="')[1].split('"')[0]
    print(f"   {meta_url}\n   {httpx.get(meta_url).json()}")

    print("\n3. a wrong token")
    r = httpx.post(url, json=body, headers={**hdr, "authorization": "Bearer not-a-real-token"})
    print(f"   HTTP {r.status_code} {r.json()}")

    print("\n4. read-only token (scope acme:read) through the MCP SDK client")
    with MCPToolbox({"acme": HttpTarget(url, {"Authorization": f"Bearer {read}"})},
                    elicitation=scripted_elicitation([True])) as box:
        print(f"   protocol {box.clients['acme'].protocol_version}, {len(box.tools())} tools listed")
        ok = box([ToolCall("1", "acme__check_policy", {"system": "figma", "access_level": "editor",
                                                       "external_sharing": False}, "")])[0]
        print(f"   check_policy -> {ok.text[:110]}...")
        no = box([ToolCall("2", "acme__create_access_request", ARGS, "")])[0]
        print(f"   create_access_request -> is_error={no.is_error}: {no.text[:120]}")

    print("\n5. full token (acme:read acme:write); the human approves in the elicitation")
    asked = []
    with MCPToolbox({"acme": HttpTarget(url, {"Authorization": f"Bearer {full}"})},
                    elicitation=scripted_elicitation([True], asked)) as box:
        res = box([ToolCall("3", "acme__create_access_request", ARGS, "")])[0]
        print(f"   the server asked: {asked[0][:120]}...")
        print(f"   create_access_request -> is_error={res.is_error}: {res.text[:120]}...")
finally:
    proc.terminate()
    proc.wait(timeout=5)
