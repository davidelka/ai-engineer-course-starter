"""llmkit.structured against the mock server: native schemas for 3 providers, repairs, failures."""

import json
import random
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from llmkit import LLM, RetryPolicy
from llmkit.providers.openai import OpenAIProvider
from llmkit.structured import (StructuredError, complete_structured, extract_json, format_errors,
                               provider_schema)
from mockllm import MockConfig, start_in_thread
from mockllm.server import request_schema

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "labs" / "03-structured-outputs"))
from acme_schema import AccessRequest  # noqa: E402

PROVIDERS = ["anthropic", "openai", "gemini"]


@pytest.fixture(scope="module")
def _server():
    server, url = start_in_thread(MockConfig())
    yield server, url
    server.shutdown()


@pytest.fixture
def mock(_server):
    server, url = _server
    server.state.cfg = MockConfig(ttft=0, tps=0, seed=1)
    server.state.rng.seed(1)
    server.state.reset()
    return server, url


def llm(url, provider="anthropic"):
    return LLM(f"{provider}:mock-model", api_key="t", base_url=url,
               retry=RetryPolicy(sleep=lambda s: None, rng=random.Random(0)))


# ---------------------------------------------------------------- schema transform
@pytest.mark.parametrize("provider", PROVIDERS)
def test_schema_is_strict(provider):
    schema, notes = provider_schema(AccessRequest, provider)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "default" not in json.dumps(schema)


def test_unsupported_constraints_move_to_description():
    schema, notes = provider_schema(AccessRequest, "anthropic")
    dur = json.dumps(schema["properties"]["duration_days"])
    assert '"minimum"' not in dur and "minimum=1" in dur
    assert any("duration_days" in n for n in notes)
    assert '"pattern"' not in json.dumps(schema["properties"]["requester_email"])  # Claude: "Schema is too complex"
    gem, _ = provider_schema(AccessRequest, "gemini")
    assert '"pattern"' not in json.dumps(gem["properties"]["requester_email"])
    oai, _ = provider_schema(AccessRequest, "openai")
    assert '"pattern"' in json.dumps(oai["properties"]["requester_email"])  # OpenAI strict accepts it


@pytest.mark.parametrize("provider", PROVIDERS)
def test_schema_lands_where_each_provider_expects_it(provider):
    from llmkit.types import ChatRequest
    p = llm("http://x", provider).provider
    schema, _ = provider_schema(AccessRequest, provider)
    req = ChatRequest.from_prompt("hi", response_schema=schema, effort="low")
    body = p.build(req, "m", "k", stream=False).body
    assert request_schema(provider, body) == schema
    if provider == "anthropic":
        assert body["output_config"]["effort"] == "low"  # format merges with effort, does not replace it


# ---------------------------------------------------------------- happy path and repairs
@pytest.mark.parametrize("provider", PROVIDERS)
def test_native_returns_a_model_instance(mock, provider):
    res = complete_structured(llm(mock[1], provider), "Read access to Jira", AccessRequest)
    assert isinstance(res.value, AccessRequest) and res.attempts == 1 and res.cost_usd > 0


@pytest.mark.parametrize("fault", ["missing_field", "wrong_type", "bad_enum", "extra_field", "out_of_range", "truncated"])
def test_one_broken_reply_is_repaired(mock, fault):
    server, url = mock
    server.state.cfg.json_fault, server.state.cfg.json_fault_first = fault, 1
    res = complete_structured(llm(url), "Read access to Jira", AccessRequest)
    assert res.attempts == 2 and len(res.errors) == 1


def test_extra_field_is_an_error_not_silently_dropped(mock):
    server, url = mock
    server.state.cfg.json_fault, server.state.cfg.json_fault_first = "extra_field", 1
    res = complete_structured(llm(url), "x", AccessRequest)
    assert "notes" in res.errors[0]


def test_repairs_are_sent_back_to_the_model(mock):
    server, url = mock
    server.state.cfg.json_fault, server.state.cfg.json_fault_first = "bad_enum", 1
    complete_structured(llm(url), "x", AccessRequest)
    assert server.state.requests == 2


def test_gives_up_after_max_repairs(mock):
    server, url = mock
    server.state.cfg.json_fault, server.state.cfg.json_fault_first = "bad_enum", 100
    with pytest.raises(StructuredError) as e:
        complete_structured(llm(url), "x", AccessRequest, max_repairs=2)
    assert e.value.stage == "invalid" and len(e.value.errors) == 3 and e.value.result.cost_usd > 0


def test_max_tokens_is_not_repaired(mock):
    server, url = mock
    with pytest.raises(StructuredError) as e:
        complete_structured(llm(url), "x", AccessRequest, max_tokens=5)
    assert e.value.stage == "truncated" and server.state.requests == 1


def test_prompt_mode_with_fenced_reply(mock):
    server, url = mock
    obj = dict(tool="Jira", access_level="read", production=False, customer_data=False, financial_data=False,
               external_sharing=False, reason="r", route="auto_approve")
    server.state.cfg.reply = json.dumps(obj)
    server.state.cfg.json_fault, server.state.cfg.json_fault_first = "fence", 1
    res = complete_structured(llm(url), "x", AccessRequest, mode="prompt")
    assert res.value.tool == "Jira" and res.attempts == 1


def test_openai_refusal_is_detected():
    body = {"id": "r1", "status": "completed", "usage": {"input_tokens": 1, "output_tokens": 1},
            "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "I can't help."}]}]}
    parsed = OpenAIProvider().parse(body, {})
    assert parsed.raw_stop == "refusal" and OpenAIProvider().map_stop(parsed.raw_stop) == "refusal"


# ---------------------------------------------------------------- reference helpers
def test_reference_extract_json():
    assert json.loads(extract_json('ok ```json\n{"a": "}"}\n``` bye')) == {"a": "}"}
    with pytest.raises(ValueError):
        extract_json('{"a": ')


def test_reference_format_errors():
    with pytest.raises(ValidationError) as e:
        AccessRequest.model_validate({"tool": "x"})
    text = format_errors(e.value)
    assert text.startswith("- ") and "route" in text
