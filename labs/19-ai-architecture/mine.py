"""Your code for lesson 19. Each part is checked by tests in ./tests.

The reference versions live in archkit/ (cost.py, latency.py, rules.py, mermaid.py).
Try not to read them before your tests pass.

    python -m pytest -q labs/19-ai-architecture/tests

What you have to work with
--------------------------
llmkit.pricing.PRICES   USD per 1M tokens, e.g. PRICES["claude-haiku-5-5"] ==
                        {"input": 0.10, "output": 0.50, "cached_input": 0.01, "cache_write": 0.125, ...}
llmkit.pricing.cost_usd(model, Usage(input_tokens=, output_tokens=, cached_input_tokens=,
                                     cache_creation_tokens=))
                        -> USD for one call. input_tokens is the WHOLE prompt (cache reads and
                        writes included). cost_usd bills cache reads at "cached_input", cache
                        writes at "cache_write" (input price when the model has none), the rest
                        at "input", output at "output", and applies the long-context multiplier.
archkit.spec.Spec       the architecture spec (see specs/company_brain.arch.yaml).
                        Helpers: spec.components, spec.flows, spec.component(id),
                        spec.has_component(id), spec.trust_of(id) -> "untrusted" |
                        "trusted" | "third_party", spec.outgoing(id), spec.incoming(id),
                        spec.by_kind("llm", ...). A flow has .src, .dst, .data,
                        .classification ("public"|"internal"|"confidential"|"pii") and .key ("src->dst").
archkit.rules.Finding   Finding(rule, severity, where, message), severity "error" | "warning".
"""

from __future__ import annotations

from typing import Iterable

from archkit.cost import CallProfile  # noqa: F401
from archkit.latency import Stage  # noqa: F401
from archkit.rules import Finding
from archkit.spec import FALLBACK_MODES, Spec  # noqa: F401
from llmkit.pricing import PRICES, cost_usd  # noqa: F401
from llmkit.types import Usage  # noqa: F401


# ------------------------------------------------------------------ exercise 1
def request_cost(calls: Iterable[CallProfile], prompt_cache_hit_rate: float = 0.0) -> float:
    """Expected USD of ONE request that makes all of these model calls.

    calls: CallProfile(name, model, input_tokens, output_tokens, cacheable_tokens=...,
    calls_per_request=...). calls_per_request weights a call (0.3 = runs on 30% of requests,
    1.2 = retries). prompt_cache_hit_rate h in [0, 1]: the share of calls whose cacheable prefix
    (at most input_tokens) is read from the prompt cache. When h > 0 caching is on, so a miss
    WRITES that prefix to the cache; when h == 0 there is no caching at all.
    Returns a float, the expected cost in USD, priced with llmkit.pricing.cost_usd.
    Raises ValueError if a call's model is not in PRICES.

    Stuck? HINTS.md -> request_cost
    """
    # TODO(ex1)
    raise NotImplementedError("exercise 1: implement request_cost")


def monthly_cost(calls: Iterable[CallProfile], requests_per_day: float, *, days: int = 30,
                 prompt_cache_hit_rate: float = 0.0, response_cache_hit_rate: float = 0.0,
                 fixed_monthly_usd: float = 0.0) -> dict:
    """Monthly cost of one request path. Returns a dict with exactly these keys:

      per_request_usd     the cost of one request that reaches the model (prompt caching included)
      requests_month      all requests in `days` days
      llm_requests_month  requests that reach the model (a response-cache hit is answered by
                          OUR cache: no model call at all)
      llm_monthly_usd     model spend for the month
      fixed_monthly_usd   as given (hosting, database, tracing plan...)
      total_monthly_usd   model spend plus fixed costs

    Stuck? HINTS.md -> monthly_cost
    """
    # TODO(ex1)
    raise NotImplementedError("exercise 1: implement monthly_cost")


# ------------------------------------------------------------------ exercise 2
def latency_budget(stages: Iterable[Stage], budget_ms: float) -> dict:
    """Compose a conservative p95 latency budget.

    Stages run in the order given; stages that share a `group` run IN PARALLEL and form one block
    named after the group, at the position of its first member. A stage with group=None is a block
    of its own, named after the stage. Parallel blocks cost their slowest member; the total is
    conservative (p95 values are added, not combined statistically).

    Returns a dict with exactly these keys:
      blocks [(name, p95_ms), ...] in order, total_p95_ms, budget_ms (as given),
      slack_ms (negative when over budget), within_budget (bool, equal counts as within),
      largest (block name, None if there are no stages), shares {block name: fraction of total}
      (0.0 when the total is 0).

    Example: [A 100], [B 300, group g], [C 200, group g], [D 50], budget 500
      -> blocks [("A",100), ("g",300), ("D",50)], total 450, slack 50, largest "g"

    Stuck? HINTS.md -> latency_budget
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement latency_budget")


# ------------------------------------------------------------------ exercise 3
# A worked example rule (already done, read it): every path from an untrusted
# component to an LLM or a tool must pass through a guardrail.
def rule_external_input_guarded(spec: Spec) -> list[Finding]:
    out: list[Finding] = []
    for src in spec.components:
        if spec.trust_of(src.id) != "untrusted":
            continue
        seen, stack, reported = {src.id}, [(src.id, [src.id])], set()
        while stack:                                   # depth-first walk along the flows
            node, path = stack.pop()
            for f in spec.outgoing(node):
                nxt = spec.component(f.dst)
                if nxt.kind == "guardrail":
                    continue                           # checked: stop walking this branch
                if spec.trust_of(nxt.id) == "untrusted":
                    continue                           # another source: checked on its own
                if nxt.kind in ("llm", "tool"):
                    if nxt.id not in reported:
                        reported.add(nxt.id)
                        out.append(Finding("external_input_guarded", "error", nxt.id,
                                           f"untrusted input from {src.id} reaches {nxt.kind} {nxt.id} "
                                           f"without a guardrail: {' -> '.join(path + [nxt.id])}"))
                    continue
                if nxt.id not in seen:
                    seen.add(nxt.id)
                    stack.append((nxt.id, path + [nxt.id]))
    return out


def rule_llm_resilience(spec: Spec) -> list[Finding]:
    """Every component with kind == "llm" needs a timeout, retries and a fallback.

    Returns a list of Finding(rule="llm_resilience", severity, where=<llm component id>, message).
    One finding per problem (several problems on one component give several findings):
      - no positive timeout_s                  -> error, message contains "timeout"
      - no retry with at least 2 attempts      -> error, message contains "retry"
      - no fallback                            -> error, message contains "fallback"
      - fallback is the component itself       -> error, message contains "itself"
      - fallback is neither a mode in FALLBACK_MODES nor a component id
                                               -> error, message contains "fallback" and the value
      - fallback is another llm in the SAME boundary
                                               -> WARNING, message contains "same boundary"
    A fallback mode from FALLBACK_MODES is fine. Non-llm components are ignored.

    Stuck? HINTS.md -> rule_llm_resilience
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement rule_llm_resilience")


def rule_pii_classified(spec: Spec) -> list[Finding]:
    """PII never reaches a third party without a classification step.

    Returns a list of Finding(rule="pii_classified", severity="error", where=<flow key "src->dst">,
    message). Only flows into a component in a "third_party" boundary that does NOT have
    pii_allowed=True are checked. Such a flow is a finding when:
      - it is itself classified "pii": message contains "pii" and the destination id; or
      - pii reaches its source from upstream without passing a component of kind "classifier"
        (a classifier as the source itself counts): message contains the id of the component
        the pii came from.
    At most one finding per flow. Specs can contain cycles.

    Stuck? HINTS.md -> rule_pii_classified
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement rule_pii_classified")


# ------------------------------------------------------------------ exercise 5
def to_mermaid(spec: Spec) -> str:
    """Generate a Mermaid flowchart from the spec. The output must follow this contract:

      line 1:  flowchart LR
      for each boundary that has components, in spec order:
               subgraph b_<boundary id>["<boundary name> · <trust>"]
                 c_<id><open>"<name><br/><small><meta></small>"<close>     (one line per component)
               end
        <meta> = kind, plus " · " + tech if tech is set, else " · " + model if model is set
        shapes (<open>/<close>): llm {{ }}, datastore and cache [( )],
                                 guardrail and classifier [[ ]], human_approval [/ /], others [ ]
      one edge per flow, in spec order:
               c_<src> -->|"<data>"| c_<dst>
        for pii flows use ==> instead of --> and append " (pii)" to the label
      then, in component order, for each component whose fallback is ANOTHER component id:
               c_<id> -.->|"fallback"| c_<fallback id>
        (fallback modes like static_message are not components: no edge)
      styling (optional for the tests, nice for the eye): classDef lines + "class c_a,c_b llm"
    Escape double quotes inside names/labels as #quot; . Return the text ending with "\\n".
    Prefixes b_ and c_ matter: a node id "end" breaks Mermaid.

    Stuck? HINTS.md -> to_mermaid
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement to_mermaid")
