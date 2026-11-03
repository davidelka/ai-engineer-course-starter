"""gatewaykit (lesson 25): the whole pipeline against local mock servers. Offline, free."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gatewaykit.app import create_app
from gatewaykit.audit import AuditLog, cost_report, prune, read_audit
from gatewaykit.budget import BudgetLedger, BudgetLimit, UnknownPriceError, estimate_max_cost, spend_from_usage
from gatewaykit.config import load_config, parse_config
from gatewaykit.gateway import Gateway
from gatewaykit.keys import KeyStore, hash_key
from gatewaykit.policy import decide, effective_classification, load_policy
from gatewaykit.redact import redact
from gatewaykit.router import CircuitBreaker
from gatewaykit.wire import parse_anthropic, parse_openai
from llmkit import LLM, LLMError, RetryPolicy
from llmkit.types import ChatRequest, Message, Usage
from mockllm import MockConfig, start_in_thread

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "25-llm-gateway"

POLICY = {
    "classifications": ["public", "internal", "confidential", "restricted"],
    "default_classification": "internal",
    "rules": {
        "public": {"providers": ["anthropic", "openai"], "redact": ["email", "phone_il", "il_id"]},
        "internal": {"providers": ["anthropic", "openai"], "redact": ["phone_il", "il_id"]},
        "confidential": {"providers": ["anthropic"], "regions": ["us", "eu"], "redact": ["phone_il", "il_id"]},
        "restricted": {"deny": True, "reason": "no"},
    },
}


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def mocks():
    servers = {}
    for name, cfg in {"a": MockConfig(), "b": MockConfig(), "down": MockConfig(fail_rate=1.0, status=529)}.items():
        servers[name] = start_in_thread(cfg)
    yield {k: v[1] for k, v in servers.items()}, {k: v[0] for k, v in servers.items()}
    for srv, _ in servers.values():
        srv.shutdown()


def config(urls, **extra):
    data = {
        "model_list": [
            {"model_name": "haiku", "deployments": [
                {"id": "anthropic-us", "model": "anthropic:mock-model", "base_url": urls["a"], "api_key": "m", "region": "us"},
                {"id": "openai-global", "model": "openai:mock-model", "base_url": urls["b"], "api_key": "m",
                 "region": "global"}]},
            {"model_name": "flaky", "deployments": [
                {"id": "down", "model": "anthropic:mock-model", "base_url": urls["down"], "api_key": "m", "region": "us"},
                {"id": "backup", "model": "anthropic:mock-model", "base_url": urls["b"], "api_key": "m", "region": "us"}]},
            {"model_name": "sonnet", "deployments": [
                {"id": "sonnet-us", "model": "anthropic:mock-sonnet", "base_url": urls["a"], "api_key": "m",
                 "region": "us", "prices": {"input": 2.0, "output": 10.0}}]},
        ],
        "router": {"retries_per_deployment": 0, "failure_threshold": 2, "cooldown_s": 30},
    }
    data.update(extra)
    return parse_config(data)


def make(urls, tmp_path=None, keys=None, clock=None, **gw_kw):
    cfg = config(urls, **gw_kw.pop("cfg_extra", {}))
    if tmp_path is not None:
        cfg.audit_path = tmp_path / "audit.jsonl"
    store = KeyStore()
    raw = {}
    for spec in keys or [dict(key_id="app", team="support")]:
        spec = dict(spec)
        r, _ = store.create(spec.pop("key_id"), spec.pop("team"), **spec)
        raw[_.key_id] = r
    clock = clock or Clock()
    gw = Gateway(cfg, store, POLICY, audit=AuditLog(cfg.audit_path), clock=clock, monotonic=clock, **gw_kw)
    return gw, raw


def chat(gw, key, model="haiku", text="hello", headers=None, max_tokens=50, flavor="openai"):
    h = {"authorization": f"Bearer {key}"} if key else {}
    h.update(headers or {})
    body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": text}]}
    return gw.handle(flavor, h, body)


def answer(resp):
    return resp.body["choices"][0]["message"]["content"]


# ---------------------------------------------------------------- config and keys
def test_unpriced_model_refuses_to_start(mocks):
    urls, _ = mocks
    with pytest.raises(ValueError, match="no price"):
        parse_config({"model_list": [{"model_name": "x", "deployments": [
            {"id": "x", "model": "anthropic:who-knows", "base_url": urls["a"], "api_key": "m"}]}]})


def test_raw_prompt_logging_is_not_an_option(mocks):
    urls, _ = mocks
    with pytest.raises(ValueError, match="log_content"):
        config(urls, audit={"log_content": "full"})


def test_lab_config_and_policy_load():
    cfg = load_config(LAB / "gateway.yaml")
    assert set(cfg.models) == {"haiku", "sonnet", "gpt", "haiku-flaky"}
    assert cfg.policy_path == LAB / "policy.yaml"
    pol = load_policy(cfg.policy_path)
    assert pol["rules"]["restricted"]["deny"] is True
    live = load_config(LAB / "gateway.live.yaml")
    assert live.models["haiku"].deployments[0].model == "claude-haiku-5-5"


def test_key_store_keeps_only_hashes(tmp_path):
    store = KeyStore.load(tmp_path / "keys.yaml")
    raw, vk = store.create("app", "support", models=["haiku"])
    assert raw.startswith("sk-gw-") and vk.sha256 == hash_key(raw)
    text = (tmp_path / "keys.yaml").read_text()
    assert raw not in text and vk.sha256 in text
    again = KeyStore.load(tmp_path / "keys.yaml")
    assert again.lookup(raw).key_id == "app"
    assert again.lookup("sk-gw-nope") is None
    again.revoke("app")
    assert KeyStore.load(tmp_path / "keys.yaml").by_id("app").revoked


# ---------------------------------------------------------------- the pipeline, step by step
def test_happy_path_headers_and_audit(mocks):
    urls, _ = mocks
    gw, raw = make(urls)
    r = chat(gw, raw["app"])
    assert r.status == 200 and "You asked: hello" in answer(r)
    assert r.headers["x-gateway-deployment"] == "anthropic-us"
    assert float(r.headers["x-gateway-cost-usd"]) > 0
    rec = gw.audit.memory[-1]
    assert rec["key_id"] == "app" and rec["team"] == "support" and rec["status"] == 200
    assert rec["classification"] == "internal" and rec["cost_usd"] > 0
    assert "hello" not in json.dumps(rec), "the prompt is not logged by default"


def test_auth_failures_are_401_and_audited(mocks):
    urls, _ = mocks
    gw, raw = make(urls)
    assert chat(gw, None).status == 401
    r = chat(gw, "sk-gw-guess")
    assert r.status == 401 and r.body["error"]["type"] == "authentication_error"
    assert gw.audit.memory[-1]["reason"] == "invalid_key" and gw.audit.memory[-1]["key_hint"].startswith("...")
    gw.keys.revoke("app")
    r = chat(gw, raw["app"])
    assert r.status == 401 and gw.audit.memory[-1]["reason"] == "revoked_key"
    assert gw.audit.memory[-1]["key_id"] == "app", "a revoked key in use is a signal: we know whose it was"


def test_allow_list_unknown_model_and_bad_params(mocks):
    urls, _ = mocks
    gw, raw = make(urls, keys=[dict(key_id="app", team="t", models=["haiku"])])
    assert chat(gw, raw["app"], model="sonnet").status == 403
    assert chat(gw, raw["app"], model="nope").status == 404
    r = gw.handle("openai", {"authorization": f"Bearer {raw['app']}"},
                  {"model": "haiku", "temperature": 0, "messages": [{"role": "user", "content": "x"}]})
    assert r.status == 400 and "temperature" in r.body["error"]["message"]
    r = gw.handle("openai", {"authorization": f"Bearer {raw['app']}"},
                  {"model": "haiku", "stream": True, "messages": [{"role": "user", "content": "x"}]})
    assert r.status == 400


def test_restricted_is_denied_with_the_rule(mocks):
    urls, _ = mocks
    gw, raw = make(urls)
    r = chat(gw, raw["app"], headers={"x-data-classification": "restricted"})
    assert r.status == 403 and r.body["error"]["type"] == "policy_denied"
    assert "restricted.deny" in r.body["error"]["message"]
    assert chat(gw, raw["app"], headers={"x-data-classification": "secret"}).status == 400


def test_floor_cannot_be_lowered(mocks):
    urls, _ = mocks
    gw, raw = make(urls, keys=[dict(key_id="hr", team="hr", classification_floor="confidential")])
    r = chat(gw, raw["hr"], headers={"x-data-classification": "public"})
    assert r.headers["x-gateway-classification"] == "confidential"


def test_fallback_never_crosses_the_policy(mocks):
    """Confidential + primary down: the openai deployment is healthy but forbidden -> 503, and it got nothing."""
    urls, servers = mocks
    gw, raw = make(urls, keys=[dict(key_id="hr", team="hr", classification_floor="confidential")])
    servers["a"].state.cfg.fail_rate, servers["a"].state.cfg.status = 1.0, 503
    before = servers["b"].state.requests
    r = chat(gw, raw["hr"])
    assert r.status == 503 and r.body["error"]["type"] == "upstream_unavailable"
    assert servers["b"].state.requests == before
    assert [p["rule"] for p in gw.audit.memory[-1]["policy"]] == ["confidential.allow", "confidential.providers"]


def test_internal_traffic_does_fall_back(mocks):
    urls, servers = mocks
    gw, raw = make(urls)
    servers["a"].state.cfg.fail_rate, servers["a"].state.cfg.status = 1.0, 503
    r = chat(gw, raw["app"])
    assert r.status == 200 and r.headers["x-gateway-deployment"] == "openai-global"
    assert r.headers["x-gateway-attempts"] == "anthropic-us:error/503,openai-global:ok"


def test_circuit_opens_and_stops_hitting_the_dead_deployment(mocks):
    urls, servers = mocks
    clock = Clock()
    gw, raw = make(urls, clock=clock)
    for _ in range(5):
        assert chat(gw, raw["app"], model="flaky").status == 200
    assert servers["down"].state.requests == 2, "threshold 2: after that the breaker skips it"
    assert gw.breakers["down"].state == "open"
    clock.t += 30
    chat(gw, raw["app"], model="flaky")
    assert servers["down"].state.requests == 3, "after the cooldown: exactly one trial"


def test_non_retryable_upstream_error_is_passed_through_without_fallback(mocks):
    urls, servers = mocks
    gw, raw = make(urls)
    servers["a"].state.cfg.fail_rate, servers["a"].state.cfg.status = 1.0, 400
    before = servers["b"].state.requests
    r = chat(gw, raw["app"])
    assert r.status == 400 and servers["b"].state.requests == before
    assert gw.breakers["anthropic-us"].state == "closed"


def test_upstream_auth_failure_is_502_not_401(mocks):
    urls, servers = mocks
    gw, raw = make(urls)
    servers["a"].state.cfg.fail_rate, servers["a"].state.cfg.status = 1.0, 401
    r = chat(gw, raw["app"])
    assert r.status == 502, "the CLIENT's key is fine; the gateway's provider key is not"


# ---------------------------------------------------------------- budgets and rate limits
def test_budget_402_from_estimate_and_soft_warning(mocks):
    urls, _ = mocks
    gw, raw = make(urls, keys=[dict(key_id="fin", team="finance", max_budget_usd=0.002, soft_budget_usd=0.0005)])
    r = chat(gw, raw["fin"], model="sonnet", max_tokens=1024)
    assert r.status == 402 and r.body["error"]["type"] == "budget_exceeded"
    statuses, warnings = [], []
    for _ in range(20):
        r = chat(gw, raw["fin"], model="sonnet", max_tokens=50)
        statuses.append(r.status)
        warnings.append(r.headers.get("x-gateway-warning"))
        if r.status != 200:
            break
    assert statuses[-1] == 402 and statuses.count(200) >= 3
    assert "soft_limit" in warnings
    assert gw.ledger.spent("fin") <= 0.002, "the estimate keeps spend under the hard limit"


def test_spend_equals_sum_of_llmkit_costs_and_survives_restart(mocks, tmp_path):
    urls, _ = mocks
    keys = [dict(key_id="app", team="support", max_budget_usd=1.0, budget_period_days=30)]
    gw, raw = make(urls, tmp_path, keys=keys)
    costs = [float(chat(gw, raw["app"]).headers["x-gateway-cost-usd"]) for _ in range(3)]
    assert gw.ledger.spent("app") == pytest.approx(sum(costs))
    cfg = gw.cfg
    gw2 = Gateway(cfg, gw.keys, POLICY, audit=AuditLog(cfg.audit_path), clock=gw.clock, monotonic=gw.clock)
    assert gw2.ledger.spent("app") == pytest.approx(sum(costs), rel=1e-6)


def test_rate_limit_429_with_retry_after(mocks):
    urls, _ = mocks
    clock = Clock()
    gw, raw = make(urls, keys=[dict(key_id="app", team="t", rpm_limit=2)], clock=clock)
    assert chat(gw, raw["app"]).status == 200
    assert chat(gw, raw["app"]).status == 200
    r = chat(gw, raw["app"])
    assert r.status == 429 and int(r.headers["retry-after"]) >= 1
    clock.t += 61
    assert chat(gw, raw["app"]).status == 200


# ---------------------------------------------------------------- redaction
def test_provider_sees_placeholders_app_gets_originals(mocks):
    urls, _ = mocks
    gw, raw = make(urls)
    gw.cfg.restore_pii_in_response = False
    r = chat(gw, raw["app"], text="id 123456782 phone 054-1234567 mail a@acme.example")
    assert "[IL_ID_1]" in answer(r) and "[PHONE_IL_1]" in answer(r)
    assert "a@acme.example" in answer(r), "internal level: emails pass"
    assert r.headers["x-gateway-redactions"] == "il_id=1,phone_il=1"
    gw.cfg.restore_pii_in_response = True
    r = chat(gw, raw["app"], text="id 123456782 phone 054-1234567")
    assert "123456782" in answer(r) and "[IL_ID_1]" not in answer(r)
    dump = json.dumps(gw.audit.memory)
    assert "123456782" not in dump and "054-1234567" not in dump


def test_one_numbering_across_system_and_messages(mocks):
    urls, _ = mocks
    gw, raw = make(urls)
    gw.cfg.restore_pii_in_response = False
    seen = []
    orig = gw.llms["anthropic-us"].complete

    def spy(req, **kw):
        seen.append(req)
        return orig(req, **kw)

    gw.llms["anthropic-us"].complete = spy
    gw.handle("openai", {"authorization": f"Bearer {raw['app']}", "x-data-classification": "public"}, {
        "model": "haiku", "messages": [{"role": "system", "content": "Owner: a@x.io"},
                                       {"role": "user", "content": "Ask b@x.io, then a@x.io"}]})
    req = seen[0]
    assert req.system_text == "Owner: [EMAIL_1]"
    assert req.messages[0].text == "Ask [EMAIL_2], then [EMAIL_1]"


def test_log_content_redacted_keeps_only_redacted_text(mocks):
    urls, _ = mocks
    gw, raw = make(urls)
    gw.cfg.log_content = "redacted"
    chat(gw, raw["app"], text="my ID is 123456782")
    rec = gw.audit.memory[-1]
    assert rec["prompt_redacted"]["messages"][0][1] == "my ID is [IL_ID_1]"
    assert "123456782" not in json.dumps(rec)


# ---------------------------------------------------------------- cache
def test_cache_is_per_team(mocks):
    urls, servers = mocks
    gw, raw = make(urls, keys=[dict(key_id="s1", team="support"), dict(key_id="s2", team="support"),
                               dict(key_id="e1", team="engineering")], cfg_extra={"cache": {"enabled": True}})
    n0 = servers["a"].state.requests
    assert chat(gw, raw["s1"]).headers["x-gateway-cache"] == "miss"
    r = chat(gw, raw["s2"])
    assert r.headers["x-gateway-cache"] == "hit" and r.headers["x-gateway-deployment"] == "anthropic-us"
    assert gw.audit.memory[-1]["cost_usd"] == 0.0
    assert chat(gw, raw["e1"]).headers["x-gateway-cache"] == "miss", "another team never gets this team's answer"
    assert servers["a"].state.requests == n0 + 2


# ---------------------------------------------------------------- llmkit and HTTP
def test_llmkit_through_the_gateway(mocks):
    urls, _ = mocks
    gw, raw = make(urls, keys=[dict(key_id="app", team="t"), dict(key_id="broke", team="t", max_budget_usd=0.0)])
    client = TestClient(create_app(gw))
    llm = LLM("anthropic:haiku", base_url="http://testserver", api_key=raw["app"], http=client)
    r = llm.complete("hi from llmkit", max_tokens=40)
    assert "hi from llmkit" in r.text and r.usage.output_tokens > 0
    assert r.cost_usd is None, "'haiku' is an alias: only the gateway can price it"
    # 402 is not retryable for llmkit: exactly one request reaches the gateway
    sleeps = []
    broke = LLM("anthropic:haiku", base_url="http://testserver", api_key=raw["broke"], http=client,
                retry=RetryPolicy(sleep=sleeps.append))
    n = len(gw.audit.memory)
    with pytest.raises(LLMError) as exc:
        broke.complete("x", max_tokens=10)
    assert exc.value.status == 402 and exc.value.kind == "budget_exceeded"
    assert len(gw.audit.memory) == n + 1 and sleeps == []


def test_llmkit_metadata_carries_the_classification(mocks):
    urls, _ = mocks
    gw, raw = make(urls)
    llm = LLM("anthropic:haiku", base_url="http://testserver", api_key=raw["app"],
              http=TestClient(create_app(gw)), retry=RetryPolicy.none())
    with pytest.raises(LLMError) as exc:
        llm.complete(ChatRequest(messages=[Message("user", "x")],
                                 extra_body={"metadata": {"data_classification": "restricted"}}))
    assert exc.value.status == 403 and exc.value.kind == "policy_denied"


def test_http_endpoints_and_admin(mocks, tmp_path):
    urls, _ = mocks
    gw, raw = make(urls, master_key="sk-gw-admin-test")
    gw.keys.path = tmp_path / "keys.yaml"
    c = TestClient(create_app(gw))
    assert c.get("/health").json()["ok"]
    assert c.post("/v1/chat/completions", content=b"{not json").status_code == 400
    m = c.get("/v1/models", headers={"authorization": f"Bearer {raw['app']}"}).json()
    assert {x["id"] for x in m["data"]} == {"haiku", "flaky", "sonnet"}
    assert c.post("/admin/keys", json={"key_id": "x", "team": "t"},
                  headers={"authorization": f"Bearer {raw['app']}"}).status_code == 403
    r = c.post("/admin/keys", json={"key_id": "new", "team": "t", "models": ["haiku"], "max_budget_usd": 1.0},
               headers={"authorization": "Bearer sk-gw-admin-test"})
    new = r.json()["key"]
    assert new not in (tmp_path / "keys.yaml").read_text()
    ok = c.post("/v1/messages", headers={"x-api-key": new},
                json={"model": "haiku", "max_tokens": 20, "messages": [{"role": "user", "content": "hi"}]})
    assert ok.status_code == 200 and ok.json()["type"] == "message"
    info = c.get("/v1/key/info", headers={"authorization": f"Bearer {new}"}).json()
    assert info["max_budget_usd"] == 1.0 and info["spent_usd"] > 0
    assert c.post("/admin/keys/new/revoke", headers={"authorization": "Bearer sk-gw-admin-test"}).status_code == 200
    assert c.post("/v1/messages", headers={"x-api-key": new}, json={
        "model": "haiku", "max_tokens": 20, "messages": [{"role": "user", "content": "hi"}]}).status_code == 401
    state = c.get("/admin/state", headers={"authorization": "Bearer sk-gw-admin-test"}).json()
    assert "anthropic-us" in state["breakers"]


# ---------------------------------------------------------------- pluggable parts
def test_components_are_pluggable(mocks):
    urls, _ = mocks
    calls = {"route": 0, "redact": 0, "decide": 0}
    from gatewaykit.router import route_with_fallback

    def route(*a, **k):
        calls["route"] += 1
        return route_with_fallback(*a, **k)

    def red(*a, **k):
        calls["redact"] += 1
        return redact(*a, **k)

    def dec(*a, **k):
        calls["decide"] += 1
        return decide(*a, **k)

    gw, raw = make(urls, ledger_factory=BudgetLedger, breaker_factory=lambda d: CircuitBreaker(1, 5),
                   route=route, redact_fn=red, decide_fn=dec, classify_fn=effective_classification)
    assert chat(gw, raw["app"], text="054-1234567").status == 200
    assert calls["route"] == 1 and calls["redact"] == 1 and calls["decide"] == 2


# ---------------------------------------------------------------- reports, retention, wire
def test_cost_report_and_prune(mocks, tmp_path):
    urls, _ = mocks
    clock = Clock(1_790_000_000.0)
    gw, raw = make(urls, tmp_path, keys=[dict(key_id="a", team="support"), dict(key_id="b", team="eng")], clock=clock)
    for _ in range(3):
        chat(gw, raw["a"])
    chat(gw, raw["b"], model="sonnet")
    chat(gw, None)
    rep = cost_report(read_audit(tmp_path / "audit.jsonl"))
    assert rep["total"]["requests"] == 5 and rep["total"]["denied"] == 1
    assert rep["by_team"]["support"]["requests"] == 3
    assert next(iter(rep["by_team"])) == "eng", "sorted by cost: one sonnet call beats three haiku calls"
    assert rep["denied_by_reason"] == {"invalid_key": 1}
    removed = prune(tmp_path / "audit.jsonl", retention_days=1, now=clock.t + 2 * 86400)
    assert removed == 5 and list(read_audit(tmp_path / "audit.jsonl")) == []


def test_wire_translation():
    model, req, meta = parse_openai({"model": "m", "user": "u1", "metadata": {"data_classification": "public"},
                                     "messages": [{"role": "system", "content": "S"},
                                                  {"role": "user", "content": [{"type": "text", "text": "A"},
                                                                               {"type": "text", "text": "B"}]}]})
    assert req.system == "S" and req.messages[0].text == "A\n\nB" and meta["end_user"] == "u1"
    with pytest.raises(ValueError):
        parse_openai({"model": "m", "messages": [{"role": "user", "content": [{"type": "image_url"}]}]})
    with pytest.raises(ValueError):
        parse_anthropic({"model": "m", "messages": [{"role": "user", "content": "x"}]})  # no max_tokens


def test_budget_helpers_fail_closed():
    with pytest.raises(UnknownPriceError):
        spend_from_usage("nope", Usage(1, 1))
    with pytest.raises(UnknownPriceError):
        estimate_max_cost("nope", 10, 10)
    led = BudgetLedger({"k": BudgetLimit(hard_usd=0.0)})
    assert led.check("k").status == 402
