"""Company Brain as an MCP server, so Claude Code / Claude Desktop can use it (lesson 17).

    python -m cbrain mcp                                   # stdio; identity from BRAIN_API_KEY
    python -m cbrain mcp --transport http --port 8766      # Streamable HTTP, bearer = a brain API key

Claude Code (stdio):
    claude mcp add company-brain --env BRAIN_API_KEY=demo-dana --env BRAIN_DEMO_KEYS=1 \\
        -- python -m cbrain mcp            (run from projects/f1-company-brain, venv active)

What is served, and what is deliberately NOT (least privilege, and the same rules as the web API):
    from mcpkit (lesson 17, unchanged): lookup_employee, get_system_info, list_access_grants,
        check_policy, get_oncall_for_service, and the two prompts.
    brain tools: ask_company_brain (the guarded knowledge path, with THE CALLER's document role),
        preview_access_request, start_access_request (asks the human through elicitation, then starts
        the flowkit workflow with the caller as requester), request_status, my_approvals.
    NOT served: read_document, search_docs and the acme://docs resources (they bypass the ACL: an
        employee's MCP client could read a confidential postmortem), create_access_request (it files
        straight into the store and skips the workflow), and any way to DECIDE a request (a decision
        is a human act in the UI; a model must never be one click from approving access).

Auth: one identity everywhere. Over HTTP the bearer token is a brain API key; BrainTokenVerifier
maps it to the Principal (subject = user id) and gives scopes acme:read (+ acme:write for filing).
Over stdio there is no transport auth: the process is launched by the user, and BRAIN_API_KEY tells
the server who that user is (MCP spec: stdio servers take credentials from the environment).

MCP spec 2026-07-28 note (lesson 17): a 2026-07-28 client gets the confirmation as an
InputRequiredResult and retries the call with the answer (multi round-trip request); a 2025-11-25
client gets elicitation/create mid-call. The SDK serves both from the same Resolve(...) parameter.
"""

# no `from __future__ import annotations` here: the MCP SDK evaluates tool signatures, and the
# Resolve(ask_human) annotation refers to a local function.

import json
import os
from typing import Annotated, Any, Optional

from mcp.server.mcpserver import (AcceptedElicitation, Context, DeclinedElicitation, Elicit, ElicitationResult,
                                  Resolve)
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field

from .auth import Principal
from .brain import Brain

READ_TOOLS = ["lookup_employee", "get_system_info", "list_access_grants", "check_policy", "get_oncall_for_service"]
ISSUER = "https://auth.acme.example"


class ConfirmStart(BaseModel):
    approve: bool = Field(description="File this access request now?")


class _No:
    def __init__(self, reason: str):
        self.reason = reason


def _text(obj: Any, is_error: bool = False) -> CallToolResult:
    t = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    sc = obj if isinstance(obj, dict) else None
    return CallToolResult(content=[TextContent(type="text", text=t)], structured_content=sc, is_error=is_error)


class BrainTokenVerifier:
    """TokenVerifier: a brain API key -> AccessToken(subject = user id). Unknown key -> None (401)."""

    def __init__(self, brain: Brain, resource: str):
        self.brain, self.resource = brain, resource

    async def verify_token(self, token: str):
        from mcp.server.auth.provider import AccessToken
        p = self.brain.keys.lookup(token)
        if p is None:
            return None
        return AccessToken(token=token, client_id="company-brain-mcp", scopes=["acme:read", "acme:write"],
                           resource=self.resource, subject=p.id, claims={"iss": ISSUER})


def auth_kwargs(brain: Brain, resource_url: str) -> dict:
    from mcp.server.auth.settings import AuthSettings
    return {"token_verifier": BrainTokenVerifier(brain, resource_url),
            "auth": AuthSettings(issuer_url=ISSUER, resource_server_url=resource_url, required_scopes=["acme:read"],
                                 validate_token_resource=True)}


def build_brain_mcp(brain: Brain, *, stdio_principal: Optional[Principal] = None, **server_kw: Any):
    from mcpkit.server import build_acme_server
    from toolkit import acme_registry

    srv = build_acme_server(acme_registry(requests_db=brain.s.requests_db), tools=READ_TOOLS, resources=False,
                            prompts=True, name="company-brain", **server_kw)

    def principal() -> Optional[Principal]:
        try:
            from mcp.server.auth.middleware.auth_context import get_access_token
            tok = get_access_token()
        except Exception:  # noqa: BLE001
            tok = None
        if tok is not None:
            return brain.users.get(tok.subject or "")
        return stdio_principal

    ro = ToolAnnotations(read_only_hint=True, open_world_hint=False)

    def ask_company_brain(question: str) -> CallToolResult:
        p = principal()
        if p is None:
            return _text("Not authenticated: set BRAIN_API_KEY for this server.", True)
        r = brain.ask(p, question)
        if "confirm" in r:
            return _text({"intent": "access_request", "message": r["answer"]["text"], "preview": {
                k: v for k, v in r["confirm"].items() if k != "confirm_token"},
                "next": "call start_access_request with the same text to file it (the user will be asked)"})
        a = r.get("answer") or {}
        return _text({"intent": (r.get("intent") or {}).get("intent"), "answer": a.get("text"),
                      "refused": a.get("refused"), "citations": [
                          {"n": c["n"], "doc_id": c["doc_id"], "section": c.get("section")} for c in a.get("citations", [])],
                      "blocked_by": a.get("blocked_by"), "document_role": p.acl_role})

    srv.add_tool(ask_company_brain, name="ask_company_brain", annotations=ro, structured_output=False,
                 description="Ask Acme's Company Brain a question about Acme policies, processes, systems, incidents or "
                             "offices (answered from Acme's documents with numbered citations, only from documents the "
                             "user may see), or a data question (tickets, employees, customers). Answers in the "
                             "question's language. Returns 'not in the documents' when the answer is not written.")

    def preview_access_request(text: str) -> CallToolResult:
        p = principal()
        if p is None:
            return _text("Not authenticated: set BRAIN_API_KEY for this server.", True)
        pv = brain.preview(p, text)
        pv.pop("confirm_token", None)
        return _text(pv, bool(pv.get("error")))

    srv.add_tool(preview_access_request, name="preview_access_request", annotations=ro, structured_output=False,
                 description="Show what an access request written in free text WOULD file: system, level, who it is "
                             "for, the policy route (auto_approve / needs_manager / needs_security) and who approves. "
                             "Files nothing.")

    def ask_human(ctx: Context, text: str):
        p = principal()
        if p is None:
            return _No("Not authenticated: set BRAIN_API_KEY for this server.")
        pv = brain.preview(p, text)
        pv.pop("confirm_token", None)
        if pv.get("error"):
            return _No(f"NOT filed: the request could not be read ({pv['error']}). Ask the user to name the system "
                       "and the access level.")
        summary = (f"File an access request as {p.name}: {pv['access_level']} on {pv['system']} for {pv['employee']}. "
                   f"Route: {pv['route']} ({pv['approver']}).")
        caps = ctx.client_capabilities
        if caps is None or caps.elicitation is None:
            return _No("NOT filed: filing needs a human confirmation and this MCP client cannot ask the user "
                       f"(no elicitation capability). Tell the user to file it in the Company Brain UI. Would file: {summary}")
        return Elicit(summary + " Approve?", ConfirmStart)

    ask_human.__qualname__ = "confirm_start_access_request"

    def start_access_request(approval: Annotated[ElicitationResult[ConfirmStart], Resolve(ask_human)],
                             text: str) -> CallToolResult:
        data = approval.data if isinstance(approval, AcceptedElicitation) else None
        if isinstance(data, _No):
            return _text(data.reason, True)
        if isinstance(approval, DeclinedElicitation) or (isinstance(data, ConfirmStart) and not data.approve):
            return _text("NOT filed: the user declined. Ask what they want to change.", True)
        if not isinstance(data, ConfirmStart):
            return _text("NOT filed: the user dismissed the confirmation.", True)
        p = principal()
        st = brain.start_request_unconfirmed(p, text)      # the human confirmed through elicitation
        return _text({k: st.get(k) for k in ("thread_id", "request_id", "status", "route", "reasons", "manager")})

    srv.add_tool(start_access_request, name="start_access_request", structured_output=False,
                 annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                                             open_world_hint=False),
                 description="File an access request (free text, e.g. 'I need a Figma editor seat for the Q4 designs') "
                             "for the current user. Always asks the user to confirm first, then starts Acme's approval "
                             "workflow; returns the request id and status. Approvals happen in the Company Brain UI.")

    def request_status(thread_id: str) -> CallToolResult:
        p = principal()
        if p is None or not brain.requests.can_view(p, thread_id):
            return _text(f"No request {thread_id} that you may see.", True)
        st = brain.requests.status(thread_id)
        return _text({k: st.get(k) for k in ("thread_id", "request_id", "status", "route", "reasons", "decision",
                                             "notifications")})

    srv.add_tool(request_status, name="request_status", annotations=ro, structured_output=False,
                 description="Status of one of your access requests (by thread id req-...): status, route, decision.")

    def my_approvals() -> CallToolResult:
        p = principal()
        if p is None:
            return _text("Not authenticated.", True)
        items = brain.requests.inbox(p)
        return _text({"pending": [{k: it.get(k) for k in ("thread_id", "employee", "system", "access_level", "gate")}
                                  for it in items],
                      "note": "Decide in the Company Brain UI: decisions are not available over MCP."})

    srv.add_tool(my_approvals, name="my_approvals", annotations=ro, structured_output=False,
                 description="Access requests waiting for the current user's decision (read-only list).")
    return srv


def main(argv: Optional[list] = None) -> None:
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="python -m cbrain mcp")
    ap.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args(argv)
    brain = Brain.from_env()
    if a.transport == "stdio":
        p = brain.keys.lookup(os.environ.get("BRAIN_API_KEY", ""))
        if p is None:
            raise SystemExit("Set BRAIN_API_KEY to your Company Brain key (with BRAIN_DEMO_KEYS=1, e.g. demo-dana).")
        build_brain_mcp(brain, stdio_principal=p).run("stdio")
    else:
        url = f"http://{a.host}:{a.port}/mcp"
        srv = build_brain_mcp(brain, **auth_kwargs(brain, url))
        print(f"company-brain MCP on {url} (bearer = a Company Brain API key)", file=sys.stderr)
        srv.run("streamable-http", host=a.host, port=a.port)
