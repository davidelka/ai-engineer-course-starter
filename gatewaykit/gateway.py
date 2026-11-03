"""The request pipeline, independent of any web framework.

    Gateway.handle(flavor, headers, body) -> GatewayResponse(status, headers, body)

app.py wraps it in FastAPI; tests call it directly. Every step that can reject a
request returns a precise status and error type, and every request, allowed or
denied, produces exactly one audit record.

Status codes, and why:
  401 authentication_error   no key, unknown key, revoked key
  403 permission_error       the key may not use this model (allow-list)
  403 policy_denied          no deployment of this model may receive this data class
  402 budget_exceeded        the key's hard budget is spent (NOT 429: retrying will not help)
  429 rate_limit_error       the key's requests-per-minute limit; retry-after says when
  404 not_found_error        unknown model alias
  400 invalid_request_error  bad body, unsupported parameter, unknown classification
  503 upstream_unavailable   every allowed deployment failed or has an open circuit
  502 upstream_error         the provider rejected OUR credentials or answered garbage
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

from llmkit import LLM, LLMError, RetryPolicy
from llmkit.types import ChatRequest, ChatResult, Message

from . import audit as auditmod
from .budget import BudgetLedger, BudgetLimit, estimate_max_cost
from .config import Deployment, GatewayConfig
from .keys import KeyStore, VirtualKey, hash_key
from .policy import decide, effective_classification, redaction_types
from .redact import redact
from .router import AllDeploymentsFailed, CircuitBreaker, route_with_fallback
from .wire import WireError, error_body, parse_anthropic, parse_openai, render_anthropic, render_openai


@dataclass
class GatewayResponse:
    status: int
    body: dict
    headers: dict = field(default_factory=dict)


class Reject(Exception):
    def __init__(self, status: int, kind: str, message: str, headers: Optional[dict] = None, reason: str = ""):
        super().__init__(message)
        self.status, self.kind, self.message = status, kind, message
        self.headers = headers or {}
        self.reason = reason or kind


class RateLimiter:
    """Sliding 60-second window per key."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key_id: str, rpm: int) -> Optional[float]:
        """None if allowed (and counted); otherwise seconds until a slot frees up."""
        if rpm <= 0:
            return None
        now = self.clock()
        q = self.hits[key_id]
        while q and now - q[0] >= 60:
            q.popleft()
        if len(q) >= rpm:
            return max(0.0, 60 - (now - q[0]))
        q.append(now)
        return None


class ResponseCache:
    """Exact-match cache, scoped per TEAM: a cache shared across teams would hand one
    team's answer (built from its data) to another team that asked the same thing."""

    def __init__(self, ttl_s: float, clock: Callable[[], float] = time.monotonic):
        self.ttl_s, self.clock = ttl_s, clock
        self.items: dict[str, tuple[float, ChatResult, str]] = {}

    @staticmethod
    def key(team: str, model: str, req: ChatRequest) -> str:
        payload = json.dumps({"team": team, "model": model, "system": req.system_text, "max_tokens": req.max_tokens,
                              "messages": [[m.role, m.text] for m in req.messages]}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, k: str):
        hit = self.items.get(k)
        if hit and hit[0] > self.clock():
            return hit[1], hit[2]
        self.items.pop(k, None)
        return None

    def put(self, k: str, result: ChatResult, deployment: str) -> None:
        self.items[k] = (self.clock() + self.ttl_s, result, deployment)


def _limit_for(k: VirtualKey) -> BudgetLimit:
    period = k.budget_period_days * 86400 if k.budget_period_days else None
    return BudgetLimit(k.max_budget_usd, k.soft_budget_usd, period)


def default_llm_factory(dep: Deployment, prices: dict, retries: int) -> LLM:
    return LLM(dep.model_spec, api_key=dep.resolve_key(), base_url=dep.base_url, prices=prices,
               retry=RetryPolicy(max_attempts=1 + retries, base=0.2, cap=2.0))


class Gateway:
    def __init__(self, config: GatewayConfig, keys: KeyStore, policy: dict, *,
                 audit: Optional[auditmod.AuditLog] = None,
                 ledger_factory: Callable[..., Any] = BudgetLedger,
                 breaker_factory: Optional[Callable[[str], Any]] = None,
                 route: Callable[..., Any] = route_with_fallback,
                 redact_fn: Callable[..., Any] = redact,
                 decide_fn: Callable[..., Any] = decide,
                 classify_fn: Callable[..., str] = effective_classification,
                 llm_factory: Callable[[Deployment, dict, int], LLM] = default_llm_factory,
                 clock: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic,
                 master_key: Optional[str] = None,
                 pii_salt: str = ""):
        self.cfg, self.keys, self.policy = config, keys, policy
        self.audit = audit or auditmod.AuditLog(config.audit_path)
        self.clock, self.monotonic = clock, monotonic
        self.route, self.redact_fn, self.decide_fn, self.classify_fn = route, redact_fn, decide_fn, classify_fn
        self.master_key = master_key
        self.pii_salt = pii_salt
        self.prices = config.price_table()
        self.ledger = ledger_factory({k.key_id: _limit_for(k) for k in keys.all()}, clock=clock)
        breaker_factory = breaker_factory or (lambda dep_id: CircuitBreaker(
            config.failure_threshold, config.cooldown_s, clock=monotonic))
        self.breakers = {d.id: breaker_factory(d.id) for g in config.models.values() for d in g.deployments}
        # Created eagerly: a missing provider key is a startup error, not a 3am surprise.
        self.llms = {d.id: llm_factory(d, self.prices, config.retries_per_deployment)
                     for g in config.models.values() for d in g.deployments}
        self.limiter = RateLimiter(monotonic)
        self.cache = ResponseCache(config.cache_ttl_s, monotonic) if config.cache_enabled else None
        self._rebuild_spend()

    # ------------------------------------------------------------------ startup
    def _rebuild_spend(self) -> None:
        if not self.cfg.audit_path or not self.cfg.audit_path.exists():
            return
        windows = {k.key_id: (k.budget_period_days * 86400 if k.budget_period_days else None) for k in self.keys.all()}
        for key_id, spent in auditmod.rebuild_spend(auditmod.read_audit(self.cfg.audit_path), windows,
                                                    self.clock()).items():
            if spent > 0:
                self.ledger.record(key_id, spent)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def presented_key(headers: dict) -> Optional[str]:
        h = {k.lower(): v for k, v in headers.items()}
        auth = h.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return h.get("x-api-key") or None

    def _redact_request(self, req: ChatRequest, types: list[str]):
        """Redact system and every message with one shared numbering. Returns
        (new_request, findings, placeholder->original)."""
        if not types:
            return req, [], {}
        known: dict = {}
        findings, originals = [], {}

        def one(text: str) -> str:
            r = self.redact_fn(text, types, salt=self.pii_salt, known=known)
            for f in r.findings:
                originals[f.placeholder] = text[f.start:f.end]
            findings.extend(r.findings)
            return r.text

        system = one(req.system_text) if req.system_text else ""
        messages = [Message(m.role, one(m.text)) for m in req.messages]
        new = ChatRequest(messages=messages, system=system, max_tokens=req.max_tokens)
        return new, findings, originals

    def _deployments_for(self, model: str, classification: str):
        group = self.cfg.models[model]
        decisions, allowed = [], []
        for d in group.deployments:
            dec = self.decide_fn(self.policy, classification, d)
            decisions.append({"deployment": d.id, "allowed": dec.allowed, "rule": dec.rule})
            if dec.allowed:
                allowed.append(d)
        return allowed, decisions

    # ------------------------------------------------------------------ the pipeline
    def handle(self, flavor: str, headers: dict, body: Any) -> GatewayResponse:
        t0 = self.monotonic()
        rid = "gw_" + uuid.uuid4().hex[:16]
        rec: dict = {"ts": self.clock(), "request_id": rid, "endpoint": flavor, "status": 200}
        out_headers = {"x-gateway-request-id": rid}
        try:
            resp = self._pipeline(flavor, headers, body, rid, rec, out_headers)
        except Reject as r:
            rec.update(status=r.status, reason=r.reason, message=r.message[:300])
            out_headers.update(r.headers)
            resp = GatewayResponse(r.status, error_body(flavor, r.status, r.kind, r.message, rid), out_headers)
        rec["latency_ms"] = round((self.monotonic() - t0) * 1000, 1)
        self.audit.write(rec)
        return resp

    def _pipeline(self, flavor, headers, body, rid, rec, out_headers) -> GatewayResponse:
        # 1. who is calling
        raw = self.presented_key(headers)
        vk = self.keys.lookup(raw)
        if raw and not vk:
            rec["key_hint"] = "..." + hash_key(raw)[-4:]
        if not vk:
            raise Reject(401, "authentication_error", "missing or unknown virtual key", reason="invalid_key")
        rec.update(key_id=vk.key_id, team=vk.team)
        if vk.revoked:
            raise Reject(401, "authentication_error", f"virtual key {vk.key_id} was revoked", reason="revoked_key")

        # 2. what are they asking for
        try:
            model, req, meta = (parse_anthropic if flavor == "anthropic" else parse_openai)(body)
        except WireError as e:
            raise Reject(e.status, e.kind, e.message, reason="bad_request")
        rec["model"] = model
        if meta.get("end_user"):
            rec["end_user"] = str(meta["end_user"])[:64]
        if model not in self.cfg.models:
            raise Reject(404, "not_found_error", f"unknown model {model!r}; available: {sorted(self.cfg.models)}",
                         reason="unknown_model")

        # 3. may this key use this model, and this often
        if vk.models and model not in vk.models:
            raise Reject(403, "permission_error", f"key {vk.key_id} may not use model {model!r}; allowed: {vk.models}",
                         reason="model_not_allowed")
        rpm = vk.rpm_limit or self.cfg.rpm_default
        wait = self.limiter.check(vk.key_id, rpm)
        if wait is not None:
            raise Reject(429, "rate_limit_error", f"rate limit of {rpm} requests/minute reached for {vk.key_id}",
                         {"retry-after": str(max(1, round(wait)))}, reason="rate_limited")

        # 4. data classification -> which deployments may receive this request
        h = {k.lower(): v for k, v in headers.items()}
        requested = h.get("x-data-classification") or meta.get("data_classification")
        try:
            classification = self.classify_fn(requested, vk.classification_floor, self.policy)
        except ValueError as e:
            raise Reject(400, "invalid_request_error", str(e), reason="bad_classification")
        rec["classification"] = classification
        out_headers["x-gateway-classification"] = classification
        allowed, decisions = self._deployments_for(model, classification)
        rec["policy"] = decisions
        if not allowed:
            rules = ", ".join(sorted({d["rule"] for d in decisions}))
            raise Reject(403, "policy_denied",
                         f"no deployment of {model!r} may receive {classification} data (rules: {rules})",
                         reason="policy_denied")

        # 5. budget: spent so far plus the worst case of this request
        prompt_chars = len(req.system_text) + sum(len(m.text) for m in req.messages)
        estimate = estimate_max_cost(allowed[0].model, prompt_chars, req.max_tokens, self.prices)
        rec["estimated_cost_usd"] = round(estimate, 8)
        decision = self.ledger.check(vk.key_id, estimate)
        if not decision.allowed:
            raise Reject(402, "budget_exceeded",
                         f"budget exhausted for {vk.key_id}: spent ${decision.spent_usd:.6f}, "
                         f"this request could cost up to ${estimate:.6f}, remaining ${decision.remaining_usd or 0:.6f}",
                         reason="budget_exceeded")
        if decision.warning:
            out_headers["x-gateway-warning"] = decision.warning
            rec["budget_warning"] = decision.warning

        # 6. redaction, per the policy of this classification
        types = redaction_types(self.policy, classification)
        req, findings, originals = self._redact_request(req, types)
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.type] = counts.get(f.type, 0) + 1
        if counts:
            rec["redactions"] = counts
            rec["pii_fingerprints"] = sorted({f"{f.type}:{f.fingerprint}" for f in findings})
            out_headers["x-gateway-redactions"] = ",".join(f"{k}={v}" for k, v in sorted(counts.items()))
        if self.cfg.log_content == "redacted":
            rec["prompt_redacted"] = {"system": req.system_text, "messages": [[m.role, m.text] for m in req.messages]}

        # 7. cache
        ckey = self.cache.key(vk.team, model, req) if self.cache else None
        hit = self.cache.get(ckey) if self.cache else None
        if hit:
            result, dep_id = hit
            rec.update(cache_hit=True, deployment=dep_id, cost_usd=0.0,
                       usage={"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0})
            out_headers["x-gateway-cache"] = "hit"
        else:
            # 8. route, with fallback and circuit breakers
            def call(dep_id: str) -> ChatResult:
                return self.llms[dep_id].complete(req)

            try:
                routed = self.route([d.id for d in allowed], call, self.breakers)
            except AllDeploymentsFailed as e:
                rec["attempts"] = [asdict(a) for a in e.attempts]
                out_headers["x-gateway-attempts"] = ",".join(
                    f"{a.deployment}:{a.outcome}" + (f"/{a.status}" if a.status else "") for a in e.attempts)
                raise Reject(503, "upstream_unavailable", str(e), {"retry-after": "5"}, reason="all_deployments_failed")
            except LLMError as e:
                rec["upstream_error"] = {"status": e.status, "kind": e.kind}
                if e.status in (401, 403):
                    raise Reject(502, "upstream_error", "the provider rejected the gateway's credentials; "
                                 "the platform team has to fix this, not you", reason="upstream_auth")
                if e.status and 400 <= e.status < 500:
                    raise Reject(e.status, e.kind or "invalid_request_error",
                                 f"the provider rejected the request: {e.message[:200]}", reason="upstream_rejected")
                raise Reject(502, "upstream_error", f"upstream error: {e.message[:200]}", reason="upstream_error")
            result, dep_id = routed.value, routed.deployment
            rec["attempts"] = [asdict(a) for a in routed.attempts]
            rec["deployment"] = dep_id
            out_headers["x-gateway-attempts"] = ",".join(
                f"{a.deployment}:{a.outcome}" + (f"/{a.status}" if a.status else "") for a in routed.attempts)
            rec["cache_hit"] = False
            if self.cache:
                self.cache.put(ckey, result, dep_id)
                out_headers["x-gateway-cache"] = "miss"
            # 9. cost from usage -> budget
            cost = result.cost_usd if result.cost_usd is not None else 0.0
            u = result.usage
            rec.update(cost_usd=round(cost, 10), provider_model=self.cfg.deployment(dep_id).model_spec,
                       usage={"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                              "cached_input_tokens": u.cached_input_tokens})
            spent = self.ledger.record(vk.key_id, cost)
            rec["spent_after_usd"] = round(spent, 10)
            out_headers["x-gateway-cost-usd"] = f"{cost:.8f}"
            out_headers["x-gateway-spent-usd"] = f"{spent:.8f}"
            limit = self.ledger.limits.get(vk.key_id)
            if limit and limit.hard_usd is not None:
                out_headers["x-gateway-budget-remaining-usd"] = f"{max(0.0, limit.hard_usd - spent):.8f}"
        out_headers["x-gateway-deployment"] = rec["deployment"]

        # 10. answer, with placeholders restored if configured
        text = result.text
        if self.cfg.log_content == "redacted":
            rec["response_redacted"] = self.redact_fn(text, types or ["email", "phone_il", "il_id"],
                                                      salt=self.pii_salt).text
        if self.cfg.restore_pii_in_response and originals:
            for ph, orig in originals.items():
                text = text.replace(ph, orig)
        shown = ChatResult(**{**result.__dict__, "text": text})
        render = render_anthropic if flavor == "anthropic" else render_openai
        return GatewayResponse(200, render(shown, model, rid), out_headers)

    # ------------------------------------------------------------------ small endpoints
    def key_info(self, headers: dict) -> GatewayResponse:
        vk = self.keys.lookup(self.presented_key(headers))
        if not vk or vk.revoked:
            return GatewayResponse(401, error_body("openai", 401, "authentication_error", "invalid key"))
        limit = self.ledger.limits.get(vk.key_id)
        return GatewayResponse(200, {"key_id": vk.key_id, "team": vk.team, "models": vk.models or sorted(self.cfg.models),
                                     "spent_usd": self.ledger.spent(vk.key_id),
                                     "max_budget_usd": limit.hard_usd if limit else None,
                                     "soft_budget_usd": limit.soft_usd if limit else None,
                                     "classification_floor": vk.classification_floor})

    def list_models(self, headers: dict) -> GatewayResponse:
        vk = self.keys.lookup(self.presented_key(headers))
        if not vk or vk.revoked:
            return GatewayResponse(401, error_body("openai", 401, "authentication_error", "invalid key"))
        names = [m for m in sorted(self.cfg.models) if not vk.models or m in vk.models]
        return GatewayResponse(200, {"object": "list", "data": [{"id": m, "object": "model", "owned_by": "gatewaykit"}
                                                                for m in names]})

    # ------------------------------------------------------------------ admin (master key)
    def is_admin(self, headers: dict) -> bool:
        raw = self.presented_key(headers)
        return bool(self.master_key and raw and hmac.compare_digest(raw, self.master_key))

    def admin_create_key(self, body: dict) -> GatewayResponse:
        fields = {k: body[k] for k in ("owner", "models", "max_budget_usd", "soft_budget_usd", "budget_period_days",
                                       "rpm_limit", "classification_floor") if k in body}
        try:
            raw, vk = self.keys.create(body["key_id"], body.get("team", "default"), **fields)
        except (KeyError, ValueError, TypeError) as e:
            return GatewayResponse(400, error_body("openai", 400, "invalid_request_error", str(e)))
        self.ledger.limits[vk.key_id] = _limit_for(vk)
        self.audit.write({"ts": self.clock(), "admin": "key_created", "key_id": vk.key_id, "team": vk.team,
                          "status": 200, "endpoint": "admin"})
        return GatewayResponse(200, {"key": raw, "key_id": vk.key_id,
                                     "note": "shown once: the gateway stores only its SHA-256"})

    def admin_revoke(self, key_id: str) -> GatewayResponse:
        try:
            vk = self.keys.revoke(key_id)
        except KeyError:
            return GatewayResponse(404, error_body("openai", 404, "not_found_error", f"no key {key_id!r}"))
        self.audit.write({"ts": self.clock(), "admin": "key_revoked", "key_id": vk.key_id, "team": vk.team,
                          "status": 200, "endpoint": "admin"})
        return GatewayResponse(200, {"revoked": vk.key_id})

    def admin_state(self) -> GatewayResponse:
        return GatewayResponse(200, {
            "breakers": {d: getattr(b, "state", "?") for d, b in self.breakers.items()},
            "spend": {k.key_id: self.ledger.spent(k.key_id) for k in self.keys.all()},
        })
