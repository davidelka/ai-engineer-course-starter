"""gatewaykit: a small LLM gateway you can read in one sitting (lesson 25).

It sits between applications and model providers and does, in this order:

    virtual key -> rate limit -> model allow-list -> data classification policy
    -> budget check -> PII redaction -> cache -> routing with fallback and circuit
    breakers (upstream calls go through llmkit) -> cost from usage -> budget update
    -> audit log (JSONL)

Two wire formats in front: OpenAI Chat Completions (POST /v1/chat/completions) and
Anthropic Messages (POST /v1/messages), so curl, the OpenAI SDK, the Anthropic SDK
and llmkit (with base_url pointed here) can all call it. Non-streaming only, text
only: it is a teaching gateway, not LiteLLM. Every limitation is listed in
labs/25-llm-gateway/README.md.

Reference solutions for the lab live in budget.py, router.py, redact.py and
policy.py. The lab's mine.py has the same functions for you to write.
"""

from .budget import BudgetDecision, BudgetLedger, BudgetLimit, UnknownPriceError, estimate_max_cost, spend_from_usage
from .config import Deployment, GatewayConfig, ModelGroup, load_config
from .keys import KeyStore, VirtualKey, generate_key, hash_key
from .policy import PolicyDecision, decide, effective_classification, load_policy
from .redact import Finding, Redaction, israeli_id_valid, redact
from .router import AllDeploymentsFailed, Attempt, CircuitBreaker, RouteResult, route_with_fallback

__all__ = [
    "BudgetDecision", "BudgetLedger", "BudgetLimit", "UnknownPriceError", "estimate_max_cost",
    "spend_from_usage", "Deployment", "GatewayConfig", "ModelGroup", "load_config", "KeyStore",
    "VirtualKey", "generate_key", "hash_key", "PolicyDecision", "decide", "effective_classification",
    "load_policy", "Finding", "Redaction", "israeli_id_valid", "redact", "AllDeploymentsFailed",
    "Attempt", "CircuitBreaker", "RouteResult", "route_with_fallback",
]
