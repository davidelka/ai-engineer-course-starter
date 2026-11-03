"""archkit: architecture as data (lesson 19).

    spec      load and validate an architecture spec (YAML)
    rules     architecture rules that run on a spec, like a linter
    mermaid   spec -> Mermaid flowchart
    cost      tokens -> USD per request and per month (prices from llmkit.pricing)
    latency   p95 latency budget, and a Monte Carlo check of how pessimistic it is
    adr       structural lint for Architecture Decision Records
    critique  a model reviews an ADR against the rubric (structured output)
"""

from .spec import FALLBACK_MODES, Spec, SpecError, load_spec

__all__ = ["Spec", "SpecError", "load_spec", "FALLBACK_MODES"]
