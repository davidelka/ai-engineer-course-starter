"""Exercise 4: error messages a model can act on, and the repair loop."""

import random

import pytest
from pydantic import ValidationError

from acme_schema import AccessRequest
from llmkit import LLM, RetryPolicy
from llmkit.structured import complete_structured
from mine import extract_json, format_errors

GOOD = dict(requester_name="Dana", requester_email="dana@acme.example", tool="Jira", resource=None,
            access_level="read", production=False, customer_data=False, financial_data=False,
            external_sharing=False, duration_days=None, justification=None, reason="r", route="auto_approve")


def errors_for(**changes):
    data = {**GOOD, **changes}
    data = {k: v for k, v in data.items() if v != "__drop__"}
    with pytest.raises(ValidationError) as e:
        AccessRequest.model_validate(data)
    return format_errors(e.value)


def test_names_the_field_and_the_value():
    text = errors_for(duration_days=100000)
    assert "duration_days" in text and "100000" in text
    assert text.startswith("- ")


def test_missing_field():
    text = errors_for(route="__drop__")
    assert "route" in text and "required" in text.lower()


def test_bad_enum_shows_the_bad_value():
    text = errors_for(access_level="SUPER_ADMIN")
    assert "access_level" in text and "SUPER_ADMIN" in text


def test_one_line_per_error():
    text = errors_for(route="x", access_level="y", production="maybe")
    assert len([ln for ln in text.splitlines() if ln.startswith("- ")]) == 3


def test_long_values_are_cut():
    text = errors_for(access_level="A" * 500)
    assert max(len(ln) for ln in text.splitlines()) < 200 and "..." in text


def test_caps_the_number_of_lines():
    data = {k: 123 for k in GOOD}  # every string field gets an int, every bool field too
    data.update(production="?", customer_data="?", financial_data="?", external_sharing="?")
    with pytest.raises(ValidationError) as e:
        AccessRequest.model_validate(data)
    text = format_errors(e.value, max_errors=3)
    assert len(text.splitlines()) == 4 and "more errors" in text.splitlines()[-1]


def test_bad_json_message():
    try:
        extract_json('{"a": ')
    except ValueError as exc:
        assert format_errors(exc).startswith("- the reply is not valid JSON:")


@pytest.mark.parametrize("fault", ["missing_field", "bad_enum", "wrong_type", "out_of_range", "fence", "prose"])
def test_repair_loop_recovers_with_your_functions(mock, fault):
    """The first reply is broken in one way; your messages must lead to a valid second reply."""
    server, url = mock
    server.state.cfg.json_fault, server.state.cfg.json_fault_first = fault, 1
    llm = LLM("anthropic:mock-model", api_key="t", base_url=url, retry=RetryPolicy(sleep=lambda s: None, rng=random.Random(0)))
    res = complete_structured(llm, "Read access to Jira please", AccessRequest,
                              extract=extract_json, explain=format_errors, max_repairs=2)
    assert isinstance(res.value, AccessRequest)
    expected_attempts = 1 if fault in ("fence", "prose") else 2  # fences and prose are not errors for extract_json
    assert res.attempts == expected_attempts
