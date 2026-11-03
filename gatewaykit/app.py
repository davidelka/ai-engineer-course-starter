"""FastAPI wrapper around Gateway, plus build_gateway() which wires everything from a config file.

    python -m gatewaykit --config labs/25-llm-gateway/gateway.yaml --port 4100

Endpoints:
  POST /v1/chat/completions      OpenAI Chat Completions format (curl, OpenAI SDK)
  POST /v1/messages              Anthropic Messages format (Anthropic SDK, llmkit "anthropic:<alias>")
  GET  /v1/models                the models this key may use
  GET  /v1/key/info              spend and budget of the calling key
  GET  /health
  POST /admin/keys               create a key (master key)    -> the raw key, once
  POST /admin/keys/{id}/revoke   revoke a key (master key)
  GET  /admin/state              breaker states and spend per key (master key)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Optional, Union

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .audit import AuditLog
from .config import load_config
from .gateway import Gateway, GatewayResponse
from .keys import KeyStore
from .policy import load_policy
from .wire import error_body


def build_gateway(config_path: Union[str, Path], **overrides) -> Gateway:
    """Load config, keys and policy from disk and build a Gateway. overrides go to Gateway()
    (e.g. ledger_factory=mine.MyBudgetLedger, route=mine.route_with_fallback)."""
    cfg = load_config(config_path)
    keys = KeyStore.load(cfg.keys_path) if cfg.keys_path else KeyStore()
    if not cfg.policy_path:
        raise ValueError("config has no `policy:` file; a gateway without a policy allows nothing on purpose")
    policy = load_policy(cfg.policy_path)
    overrides.setdefault("master_key", os.environ.get(cfg.master_key_env) or None)
    overrides.setdefault("pii_salt", os.environ.get(cfg.pii_salt_env, ""))
    return Gateway(cfg, keys, policy, audit=AuditLog(cfg.audit_path), **overrides)


def _json(resp: GatewayResponse) -> JSONResponse:
    return JSONResponse(resp.body, status_code=resp.status, headers=resp.headers)


def create_app(gw: Gateway) -> FastAPI:
    app = FastAPI(title="gatewaykit", version="0.1", docs_url="/docs")

    async def _body(request: Request, flavor: str):
        raw = await request.body()
        try:
            return json.loads(raw or b"null"), None
        except json.JSONDecodeError:
            return None, JSONResponse(error_body(flavor, 400, "invalid_request_error", "body is not valid JSON"),
                                      status_code=400)

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        body, err = await _body(request, "openai")
        if err:
            return err
        return _json(await run_in_threadpool(gw.handle, "openai", dict(request.headers), body))

    @app.post("/v1/messages")
    async def messages(request: Request):
        body, err = await _body(request, "anthropic")
        if err:
            return err
        return _json(await run_in_threadpool(gw.handle, "anthropic", dict(request.headers), body))

    @app.get("/v1/models")
    def models(request: Request):
        return _json(gw.list_models(dict(request.headers)))

    @app.get("/v1/key/info")
    def key_info(request: Request):
        return _json(gw.key_info(dict(request.headers)))

    @app.get("/health")
    def health():
        return {"ok": True, "models": sorted(gw.cfg.models)}

    def _admin(request: Request) -> Optional[JSONResponse]:
        if not gw.is_admin(dict(request.headers)):
            return JSONResponse(error_body("openai", 403, "permission_error",
                                           "admin endpoints need the master key (GATEWAY_MASTER_KEY)"), status_code=403)
        return None

    @app.post("/admin/keys")
    async def admin_keys(request: Request):
        denied = _admin(request)
        if denied:
            return denied
        body, err = await _body(request, "openai")
        return err or _json(gw.admin_create_key(body or {}))

    @app.post("/admin/keys/{key_id}/revoke")
    def admin_revoke(key_id: str, request: Request):
        return _admin(request) or _json(gw.admin_revoke(key_id))

    @app.get("/admin/state")
    def admin_state(request: Request):
        return _admin(request) or _json(gw.admin_state())

    return app
