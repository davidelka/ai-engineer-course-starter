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

    For each call, with h = prompt_cache_hit_rate, I = input_tokens, O = output_tokens
    and K = min(cacheable_tokens, input_tokens):
      hit  = cost_usd(model, Usage(input_tokens=I, cached_input_tokens=K, output_tokens=O))
      miss = cost_usd(model, Usage(input_tokens=I, cache_creation_tokens=K, output_tokens=O))
             when h > 0 (caching is on, so a miss WRITES the prefix to the cache), or
             cost_usd(model, Usage(input_tokens=I, output_tokens=O)) when h == 0
      expected cost of the call = h * hit + (1 - h) * miss
    The request cost is the sum over calls of  call.calls_per_request * expected cost.
    (calls_per_request can be 0.3 for a call that runs on 30% of requests, or 1.2 for retries.)

    Raise ValueError if a call's model is not in PRICES.
    """
    # TODO(ex1)
    raise NotImplementedError("exercise 1: implement request_cost")


def monthly_cost(calls: Iterable[CallProfile], requests_per_day: float, *, days: int = 30,
                 prompt_cache_hit_rate: float = 0.0, response_cache_hit_rate: float = 0.0,
                 fixed_monthly_usd: float = 0.0) -> dict:
    """Monthly cost of one request path. Return a dict with exactly these keys:

      per_request_usd     request_cost(calls, prompt_cache_hit_rate, ...)
      requests_month      requests_per_day * days
      llm_requests_month  requests_month * (1 - response_cache_hit_rate)
                          (a response-cache hit is answered by OUR cache: no model call at all)
      llm_monthly_usd     per_request_usd * llm_requests_month
      fixed_monthly_usd   as given (hosting, database, tracing plan...)
      total_monthly_usd   llm_monthly_usd + fixed_monthly_usd
    """
    # TODO(ex1)
    raise NotImplementedError("exercise 1: implement monthly_cost")


# ------------------------------------------------------------------ exercise 2
def latency_budget(stages: Iterable[Stage], budget_ms: float) -> dict:
    """Compose a conservative p95 latency budget.

    Stages run in the order given. Stages with the same `group` run IN PARALLEL: the group
    is one block, worth the max p95 of its members, placed where its first member appears.
    A stage with group=None is a block of its own, named after the stage.

    Return a dict with exactly these keys:
      blocks         [(name, p95_ms), ...] in order (group blocks are named after the group)
      total_p95_ms   sum of the block values
      budget_ms      as given
      slack_ms       budget_ms - total_p95_ms (negative when over budget)
      within_budget  total_p95_ms <= budget_ms
      largest        name of the block with the largest value (None if there are no stages)
      shares         {block name: value / total} (0.0 when total is 0)

    Example: [A 100], [B 300, group g], [C 200, group g], [D 50], budget 500
      -> blocks [("A",100), ("g",300), ("D",50)], total 450, slack 50, largest "g"
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

    rule name: "llm_resilience"; where: the llm component id. For each llm component c:
      - c.timeout_s missing or <= 0            -> error, message contains "timeout"
      - c.retry missing or retry.max_attempts < 2 -> error, message contains "retry"
      - c.fallback missing                      -> error, message contains "fallback"
                                                   (then skip the fallback checks below)
      - c.fallback == c.id                      -> error, message contains "itself"
      - c.fallback in FALLBACK_MODES            -> fine
      - c.fallback is not a component id        -> error, message contains "fallback" and the bad value
      - c.fallback is another llm in the SAME boundary as c
                                                -> WARNING, message contains "same boundary"
                                                   (a fallback on the same provider does not help
                                                   when that provider is down)
    Several problems on one component give several findings.
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement rule_llm_resilience")


def rule_pii_classified(spec: Spec) -> list[Finding]:
    """PII never reaches a third party without a classification step.

    rule name: "pii_classified"; severity "error"; where: the flow key "src->dst".
    Look at every flow f whose destination is in a "third_party" boundary and whose
    destination component does NOT have pii_allowed=True (skip all other flows). Then:
      1. f.classification == "pii"  -> one finding; message contains "pii" and the destination id.
      2. otherwise, walk UPSTREAM from f.src along incoming flows:
           - a component with kind == "classifier" stops the walk on that branch
             (including f.src itself: if f.src is a classifier, the flow is fine);
           - if you meet an incoming flow g with g.classification == "pii", report ONE finding
             for f, whose message contains g.src (where the pii came from), and stop;
           - keep a `seen` set: flows can form cycles.
    At most one finding per flow.
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
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement to_mermaid")
