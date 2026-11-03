"""Exercise 5: decide which deployments may receive which data classification.

Uses the lab's real policy file, labs/25-llm-gateway/policy.yaml, and the
deployments of labs/25-llm-gateway/gateway.yaml. If you change the policy file,
some expectations below change too: that is the point of testing a policy.
"""

from pathlib import Path

import pytest

import mine
from gatewaykit.config import Deployment, load_config
from gatewaykit.policy import load_policy

LAB = Path(__file__).resolve().parent.parent
POLICY = load_policy(LAB / "policy.yaml")
CFG = load_config(LAB / "gateway.yaml")


def dep(spec, region="us"):
    return Deployment(id="t", model_spec=spec, region=region, api_key="x")


# ---------------------------------------------------------------- decide, on a small inline policy
SMALL = {
    "classifications": ["public", "internal", "confidential", "restricted", "secret"],
    "rules": {
        "public": {},
        "internal": {"providers": ["anthropic", "openai"]},
        "confidential": {"providers": ["anthropic"], "models": ["claude-haiku-5-5"], "regions": ["eu"]},
        "restricted": {"deny": True, "reason": "never to any model"},
        # "secret" is listed but has no rule
    },
}


def test_no_constraints_allows():
    d = mine.decide(SMALL, "public", dep("gemini:gemini-3.6-flash", "global"))
    assert d.allowed and d.rule == "public.allow"


def test_provider_allow_list():
    assert mine.decide(SMALL, "internal", dep("openai:gpt-5.4-mini")).allowed
    d = mine.decide(SMALL, "internal", dep("gemini:gemini-3.6-flash"))
    assert not d.allowed and d.rule == "internal.providers" and d.reason


def test_checks_run_in_order_providers_models_regions():
    assert mine.decide(SMALL, "confidential", dep("openai:gpt-5.4-mini", "us")).rule == "confidential.providers"
    assert mine.decide(SMALL, "confidential", dep("anthropic:claude-sonnet-5-5", "us")).rule == "confidential.models"
    assert mine.decide(SMALL, "confidential", dep("anthropic:claude-haiku-5-5", "us")).rule == "confidential.regions"
    d = mine.decide(SMALL, "confidential", dep("anthropic:claude-haiku-5-5", "eu"))
    assert d.allowed and d.rule == "confidential.allow"


def test_deny_rule_with_its_reason():
    d = mine.decide(SMALL, "restricted", dep("anthropic:claude-haiku-5-5"))
    assert not d.allowed and d.rule == "restricted.deny" and d.reason == "never to any model"


def test_fail_closed_on_unknown_and_missing():
    d = mine.decide(SMALL, "top-secret", dep("anthropic:claude-haiku-5-5"))
    assert not d.allowed and d.rule == "unknown_classification" and d.reason
    d = mine.decide(SMALL, "secret", dep("anthropic:claude-haiku-5-5"))
    assert not d.allowed and d.rule == "no_rule" and d.reason


# ---------------------------------------------------------------- effective classification
def test_default_is_internal_when_unlabeled():
    assert mine.effective_classification(None, None, POLICY) == "internal"
    assert mine.effective_classification("", None, POLICY) == "internal"


def test_floor_wins_when_higher():
    assert mine.effective_classification("public", "confidential", POLICY) == "confidential"
    assert mine.effective_classification(None, "confidential", POLICY) == "confidential"


def test_request_may_raise_above_the_floor():
    assert mine.effective_classification("restricted", "internal", POLICY) == "restricted"


def test_unknown_values_are_errors():
    with pytest.raises(ValueError):
        mine.effective_classification("top-secret", None, POLICY)
    with pytest.raises(ValueError):
        mine.effective_classification("public", "bogus", POLICY)


# ---------------------------------------------------------------- the lab's real policy
def matrix():
    out = {}
    for group in CFG.models.values():
        for d in group.deployments:
            for c in POLICY["classifications"]:
                out[(c, d.id)] = mine.decide(POLICY, c, d).allowed
    return out


def test_acme_policy_restricted_goes_nowhere():
    """it-ai-usage-he: Restricted data is forbidden in every AI tool, approved ones included."""
    m = matrix()
    assert not any(v for (c, _), v in m.items() if c == "restricted")


def test_acme_policy_confidential_only_to_anthropic_in_us_or_eu():
    """it-ai-usage-he: Confidential only in Claude via the company environment."""
    for group in CFG.models.values():
        for d in group.deployments:
            ok = mine.decide(POLICY, "confidential", d).allowed
            assert ok == (d.provider == "anthropic" and d.region in ("us", "eu")), d.id


def test_acme_policy_public_and_internal_reach_every_lab_deployment():
    m = matrix()
    assert all(v for (c, _), v in m.items() if c in ("public", "internal"))
