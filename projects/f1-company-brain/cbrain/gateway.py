"""Every model call through gatewaykit (lesson 25): the "production" LLM path.

    LLM_PATH=gateway                     in-process Gateway (tests, demo, a single container)
    LLM_PATH=gateway GATEWAY_URL=http://gateway:4100   a separate gateway service (compose, AWS)

What the gateway adds that the brain does not do itself:
    one virtual key per PURPOSE (brain-answer, brain-flow, brain-router), each with its own monthly
    budget, so a runaway router cannot spend the answer budget; the data-classification policy of
    labs/25-llm-gateway/policy.yaml (owned by Security, the same file lesson 25 built), so a
    confidential context can only reach an allowed deployment, even on fallback; PII redaction by
    classification; one audit record per call (JSONL, no prompt content).

Placement (ADR-0002): the gateway sits between the brain and the providers, NOT in front of the
brain. The brain knows the data classification of each call (it retrieved the chunks: milestone 7,
request_classification), so it labels the call; the gateway enforces. Auth of employees stays in
the brain, auth of applications to models in the gateway.

Limits of the teaching gateway, and how GatewayLLM handles them (measure them, do not hide them):
- text only, no streaming: GatewayLLM.stream() calls complete() and replays the text in pieces, so
  time-to-first-token equals full latency on this path (the SSE events still arrive in order).
- no native structured output (output_config is not forwarded): a request with response_schema is
  sent in PROMPT mode (llmkit.structured.schema_prompt appended to the system); complete_structured
  still validates with Pydantic and repairs once. Count the repairs in the traces.
- no prompt-cache breakpoints: the cached system block becomes plain text. LiteLLM (compose profile
  "litellm") forwards cache_control; lesson 25 compares the two.
"""

from __future__ import annotations

import contextvars
import json
import os
import secrets
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, Optional

import httpx

from llmkit.errors import LLMError
from llmkit.pricing import cost_usd
from llmkit.types import ChatRequest, ChatResult, StreamEvent, Usage, content_text

from . import ROOT
from .config import BrainSettings

POLICY_PATH = ROOT / "labs" / "25-llm-gateway" / "policy.yaml"
PURPOSES = ("answer", "flow", "router")
BUDGETS_USD = {"answer": 15.0, "flow": 5.0, "router": 2.0}     # per 30 days, for ~200 employees (see the cost model)

# The classification of the call being made right now (set by the knowledge path after retrieval).
CURRENT_CLASSIFICATION: contextvars.ContextVar[str] = contextvars.ContextVar("cbrain_classification",
                                                                              default="internal")


def _schema_prompt(req: ChatRequest) -> ChatRequest:
    if req.response_schema is None:
        return req
    sys_text = req.system_text
    schema = json.dumps(req.response_schema, ensure_ascii=False)
    extra = ("Answer with ONE JSON object and nothing else (no prose, no code fences). It must match this JSON "
             f"Schema:\n{schema}")
    return replace(req, system=(sys_text + "\n\n" if sys_text else "") + extra, response_schema=None)


class GatewayLLM:
    """llmkit-like model (complete / stream) that calls the gateway with one virtual key."""

    def __init__(self, target: Any, key: str, *, purpose: str, alias: str = "haiku",
                 model_for_price: str = "claude-haiku-5-5", timeout_s: float = 60.0):
        self.target = target               # a gatewaykit.gateway.Gateway, or a base URL string
        self._key = key
        self.purpose = purpose
        self.alias = alias
        self.model = f"gateway:{alias}"
        self.model_for_price = model_for_price
        self.provider = SimpleNamespace(name="anthropic")
        self.http = httpx.Client(timeout=timeout_s) if isinstance(target, str) else None
        self.last_headers: dict = {}

    def _body(self, req: ChatRequest) -> dict:
        req = _schema_prompt(req)
        msgs = [{"role": m.role, "content": content_text(m.content)} for m in req.messages]
        body = {"model": self.alias, "max_tokens": req.max_tokens, "messages": msgs,
                "metadata": {"data_classification": CURRENT_CLASSIFICATION.get()}}
        if req.system_text:
            body["system"] = req.system_text
        return body

    def complete(self, req: ChatRequest, **_: Any) -> ChatResult:
        body = self._body(req)
        headers = {"x-api-key": self._key, "content-type": "application/json",
                   "x-data-classification": body["metadata"]["data_classification"]}
        if self.http is not None:
            r = self.http.post(self.target.rstrip("/") + "/v1/messages", headers=headers, json=body)
            status, data, out_headers = r.status_code, r.json(), dict(r.headers)
        else:
            resp = self.target.handle("anthropic", headers, body)
            status, data, out_headers = resp.status, resp.body, resp.headers
        self.last_headers = {k.lower(): v for k, v in out_headers.items()}
        if status != 200:
            err = (data or {}).get("error", {})
            raise LLMError(f"gateway {status} {err.get('type', '')}: {err.get('message', '')}", provider="gateway",
                           status=status, kind=err.get("type", "gateway_error"))
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        u = data.get("usage") or {}
        usage = Usage(input_tokens=int(u.get("input_tokens", 0)) + int(u.get("cache_read_input_tokens", 0) or 0),
                      output_tokens=int(u.get("output_tokens", 0)),
                      cached_input_tokens=int(u.get("cache_read_input_tokens", 0) or 0))
        hdr_cost = self.last_headers.get("x-gateway-cost-usd")
        cost = float(hdr_cost) if hdr_cost is not None else cost_usd(self.model_for_price, usage)
        return ChatResult(text=text, stop_reason="end_turn", usage=usage, provider="gateway", model=self.model,
                          cost_usd=cost)

    def stream(self, req: ChatRequest, **kw: Any) -> Iterator[StreamEvent]:
        r = self.complete(req, **kw)
        words = r.text.split(" ")
        for i in range(0, len(words), 4):
            yield StreamEvent("text", " ".join(words[i:i + 4]) + (" " if i + 4 < len(words) else ""))
        yield StreamEvent("done", result=r)


# ---------------------------------------------------------------- the in-process gateway
class PricedUpstream:
    """Wraps an offline stand-in so the gateway sees a cost: usage priced AS IF it were Haiku 5.5.
    Lets the budget and the cost-per-request report work offline. Clearly an estimate."""

    def __init__(self, inner: Any, price_model: str = "claude-haiku-5-5"):
        self.inner, self.price_model = inner, price_model
        self.model = getattr(inner, "model", "offline")
        self.provider = getattr(inner, "provider", SimpleNamespace(name="anthropic"))

    def complete(self, req: ChatRequest, **kw: Any) -> ChatResult:
        r = self.inner.complete(req)
        u = r.usage
        if not u.input_tokens:
            chars = len(req.system_text) + sum(len(content_text(m.content)) for m in req.messages)
            u = Usage(input_tokens=chars // 4 + 1, output_tokens=max(1, len(r.text) // 4))
        return replace(r, usage=u, cost_usd=cost_usd(self.price_model, u))


def offline_config(audit_path: Path) -> dict:
    """The offline twin of data/gateway/gateway.yaml: same model alias and keys, fake deployments."""
    return {
        "model_list": [{"model_name": "haiku", "deployments": [
            {"id": "anthropic-us", "model": "anthropic:claude-haiku-5-5", "region": "us", "api_key": "offline"},
            {"id": "openai-global", "model": "openai:gpt-5.4-mini", "region": "global", "api_key": "offline"},
        ]}],
        "router": {"retries_per_deployment": 0, "failure_threshold": 3, "cooldown_s": 20},
        "cache": {"enabled": False},
        "audit": {"path": str(audit_path), "log_content": "none", "retention_days": 365},
        "restore_pii_in_response": True,
    }


def build_inprocess(s: BrainSettings, upstream: Any = None, *, budgets: Optional[dict] = None):
    """(gateway, {purpose: raw_key}). Offline modes get fake deployments (PricedUpstream around
    OfflineUpstream); live mode reads data/gateway/gateway.yaml (real Anthropic deployments)."""
    from gatewaykit import KeyStore, load_policy
    from gatewaykit.config import load_config, parse_config
    from gatewaykit.gateway import Gateway

    s.state_dir.mkdir(parents=True, exist_ok=True)
    policy = load_policy(POLICY_PATH)
    if s.mode == "live":
        cfg = load_config(s.gateway_config)
        cfg.audit_path = s.gateway_audit
        factory = None
    else:
        from .models import OfflineUpstream
        cfg = parse_config(offline_config(s.gateway_audit), base_dir=s.state_dir)
        up = PricedUpstream(upstream or OfflineUpstream())
        factory = lambda dep, prices, retries: up  # noqa: E731  (same fake behind every deployment)
    keys = KeyStore()
    raw: dict[str, str] = {}
    for p in PURPOSES:
        k, _ = keys.create(f"brain-{p}", team="company-brain", owner="company-brain", models=["haiku"],
                           max_budget_usd=(budgets or BUDGETS_USD)[p], budget_period_days=30,
                           classification_floor="internal", raw=secrets.token_urlsafe(24))
        raw[p] = k
    kw = {"llm_factory": factory} if factory else {}
    return Gateway(cfg, keys, policy, **kw), raw


def gateway_llms(s: BrainSettings, upstream: Any = None) -> tuple[dict[str, GatewayLLM], Any]:
    """{purpose: GatewayLLM}, plus the in-process gateway (None when GATEWAY_URL is set)."""
    if s.gateway_url:
        llms = {}
        for p in PURPOSES:
            key = os.environ.get(f"GATEWAY_KEY_{p.upper()}", "")
            if not key:
                raise SystemExit(f"GATEWAY_URL is set but GATEWAY_KEY_{p.upper()} is not (create it with gatewaykit's "
                                 "keys admin, lesson 25)")
            llms[p] = GatewayLLM(s.gateway_url, key, purpose=p)
        return llms, None
    gw, raw = build_inprocess(s, upstream)
    return {p: GatewayLLM(gw, raw[p], purpose=p) for p in PURPOSES}, gw
