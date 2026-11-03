"""Bearer-token protection for acme-mcp over Streamable HTTP (lesson 17, exercise 6).

The MCP authorization spec (2026-07-28) makes a protected MCP server an OAuth 2.1 RESOURCE
SERVER: it validates access tokens issued by an authorization server (Okta, Entra ID, Auth0,
Keycloak...) and publishes Protected Resource Metadata (RFC 9728) so a client can discover
where to get one. Running a real authorization server is out of scope for a laptop lab, so
this module plugs a STATIC token table into the SDK's TokenVerifier slot. Everything else is
the SDK's real machinery:

    - requests without a valid token get HTTP 401 with
      WWW-Authenticate: Bearer ... resource_metadata="http://127.0.0.1:8765/.well-known/oauth-protected-resource/mcp"
    - GET /.well-known/oauth-protected-resource/mcp returns the RFC 9728 document
    - every token must be issued FOR this server (resource = this server's URL): no token passthrough
    - scopes: acme:read for everything, acme:write additionally for create_access_request

Tokens come from the environment, never from code or the command line:
    ACME_MCP_TOKEN        full access   (scopes acme:read acme:write)
    ACME_MCP_TOKEN_READ   read-only     (scope acme:read)            optional
Generate one with:  python -c "import secrets; print(secrets.token_urlsafe(32))"

In production replace StaticTokenVerifier with a verifier that checks a JWT's signature, issuer,
expiry and audience (or calls the authorization server's introspection endpoint).
"""

from __future__ import annotations

import hmac
import os
from typing import Optional

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings

ISSUER = "https://auth.acme.example"  # the (pretend) authorization server named in the metadata
READ, WRITE = "acme:read", "acme:write"


class StaticTokenVerifier:
    """TokenVerifier backed by a {token: scopes} table. Constant-time comparison; unknown -> None (401)."""

    def __init__(self, tokens: dict[str, list[str]], resource: str):
        self._tokens = {t: s for t, s in tokens.items() if t}
        self.resource = resource

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        for known, scopes in self._tokens.items():
            if hmac.compare_digest(known.encode(), (token or "").encode()):
                return AccessToken(token=token, client_id="acme-lab-client", scopes=list(scopes),
                                   resource=self.resource, subject="lab-user", claims={"iss": ISSUER})
        return None


def tokens_from_env() -> dict[str, list[str]]:
    full, read = os.environ.get("ACME_MCP_TOKEN", ""), os.environ.get("ACME_MCP_TOKEN_READ", "")
    if not full and not read:
        raise SystemExit("Set ACME_MCP_TOKEN (and optionally ACME_MCP_TOKEN_READ) in the environment first. "
                         "Generate: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
    out = {}
    if full:
        out[full] = [READ, WRITE]
    if read:
        out[read] = [READ]
    return out


def auth_kwargs(resource_url: str, tokens: Optional[dict[str, list[str]]] = None) -> dict:
    """Keyword arguments for MCPServer(...): the verifier plus AuthSettings."""
    return {
        "token_verifier": StaticTokenVerifier(tokens if tokens is not None else tokens_from_env(), resource_url),
        "auth": AuthSettings(issuer_url=ISSUER, resource_server_url=resource_url, required_scopes=[READ],
                             validate_token_resource=True),
    }
