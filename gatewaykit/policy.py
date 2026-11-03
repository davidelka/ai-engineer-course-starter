"""Governance policy: which data classification may go to which provider, model and region.

Reference implementation. Exercise 5 of lab 25 asks you to write your own in mine.py.

The policy is a YAML file owned by Security, not code owned by each app team:

    classifications: [public, internal, confidential, restricted]   # low -> high
    default_classification: internal      # unlabeled data is Internal (Acme policy)
    rules:
      confidential:
        providers: [anthropic]            # optional allow-lists; missing = no constraint
        models: [claude-haiku-5-5]
        regions: [us, eu]
        redact: [phone_il, il_id]         # what the gateway removes before forwarding
      restricted:
        deny: true
        reason: "..."

Everything fails closed: an unknown classification, or a known one with no rule,
is denied. The decision always names the rule that decided it, so a denial in the
audit log can be explained to the person who got it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import yaml


@dataclass
class PolicyDecision:
    allowed: bool
    rule: str  # e.g. "confidential.providers", "restricted.deny", "internal.allow"
    reason: str = ""


def load_policy(path: Union[str, Path]) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not data.get("classifications") or not isinstance(data.get("rules"), dict):
        raise ValueError(f"{path}: a policy needs 'classifications' (a list) and 'rules' (a mapping)")
    return data


def decide(policy: dict, classification: str, deployment) -> PolicyDecision:
    """deployment: anything with .provider, .model and .region (gatewaykit.config.Deployment)."""
    c = classification
    if c not in policy.get("classifications", []):
        return PolicyDecision(False, "unknown_classification", f"classification {c!r} is not defined in the policy")
    rule = (policy.get("rules") or {}).get(c)
    if rule is None:
        return PolicyDecision(False, "no_rule", f"no rule for {c!r}: default deny")
    if rule.get("deny"):
        return PolicyDecision(False, f"{c}.deny", rule.get("reason", f"{c} data may not be sent to any model"))
    for field_name, attr in (("providers", "provider"), ("models", "model"), ("regions", "region")):
        allowed = rule.get(field_name)
        if allowed is not None and getattr(deployment, attr) not in allowed:
            return PolicyDecision(False, f"{c}.{field_name}",
                                  f"{attr} {getattr(deployment, attr)!r} is not in {field_name} for {c}: {allowed}")
    return PolicyDecision(True, f"{c}.allow", "")


def effective_classification(requested: Optional[str], floor: Optional[str], policy: dict) -> str:
    """The classification a request is handled under.

    - requested None -> policy["default_classification"] (or "internal").
    - unknown requested or floor -> ValueError (the gateway turns it into a 400).
    - result = the HIGHER of requested and floor (the key's minimum). An HR app whose
      key has floor "confidential" cannot downgrade its own traffic to "public".
    """
    order = list(policy.get("classifications", []))
    value = requested or policy.get("default_classification", "internal")
    for v in (value, floor):
        if v is not None and v not in order:
            raise ValueError(f"unknown data classification {v!r}; choose from {order}")
    if floor is not None and order.index(floor) > order.index(value):
        return floor
    return value


def redaction_types(policy: dict, classification: str) -> list[str]:
    rule = (policy.get("rules") or {}).get(classification) or {}
    return list(rule.get("redact", []))
