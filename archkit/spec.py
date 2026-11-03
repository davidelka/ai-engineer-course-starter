"""Architecture spec (lesson 19): an AI system described as data.

A spec is a YAML file with four parts:

    boundaries:  trust zones. trust = untrusted | trusted | third_party
    components:  the boxes. Each one lives in exactly one boundary.
    flows:       the arrows. Each one carries data with a classification.
    budget:      optional cost and latency model, per request path.

Because the architecture is data, rules can be checked by code (archkit.rules),
the diagram is generated instead of drawn (archkit.mermaid), and the cost model
reads the same file (archkit.cost). One source of truth, like the Pydantic model
in lesson 3.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Trust = Literal["untrusted", "trusted", "third_party"]
Kind = Literal[
    "client",          # a UI or bot the user talks to
    "service",         # our own deterministic code (API, workflow engine, router)
    "guardrail",       # checks input or output (injection, policy, citations)
    "classifier",      # a data classification / PII detection-and-redaction step
    "llm",             # a model call
    "retriever",       # search over our knowledge
    "datastore",       # database, vector store, object store
    "cache",           # response or embedding cache
    "queue",           # async buffer between parts
    "tool",            # code the model can trigger; side_effects says how dangerous
    "human_approval",  # a person decides before the flow continues
    "external_api",    # a system we do not own (Okta, Confluence, Gmail)
    "observability",   # tracing, logs, metrics
    "eval",            # offline or online evaluation
    "batch_job",       # scheduled work (ingestion, nightly reports)
]
Classification = Literal["public", "internal", "confidential", "pii"]

# A fallback is either the id of another component or one of these modes.
FALLBACK_MODES = ("static_message", "cached_response", "queue_for_human")


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    trust: Trust
    notes: str = ""


class Retry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_attempts: int = Field(ge=1, description="total attempts, including the first one")
    backoff: str = "exponential+jitter"


class Component(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    kind: Kind
    boundary: str
    tech: str = ""
    model: Optional[str] = None          # llm only, e.g. "anthropic:claude-haiku-5-5"
    timeout_s: Optional[float] = None
    retry: Optional[Retry] = None
    fallback: Optional[str] = None       # component id or one of FALLBACK_MODES
    side_effects: Literal["none", "read", "write"] = "none"
    pii_allowed: bool = False            # third party approved for PII (DPA, zero retention)
    traced: bool = False
    notes: str = ""


class Flow(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    src: str = Field(alias="from")
    dst: str = Field(alias="to")
    data: str
    classification: Classification = "internal"
    approval_exempt: Optional[str] = None  # why a write-tool flow may skip human approval

    @property
    def key(self) -> str:
        return f"{self.src}->{self.dst}"


class CallSpec(BaseModel):
    """One model call inside a request path (for the cost model)."""
    model_config = ConfigDict(extra="forbid")
    name: str
    model: str                          # a key of llmkit.pricing.PRICES
    input_tokens: int = Field(ge=0)     # everything sent: system + context + user
    output_tokens: int = Field(ge=0)
    cacheable_tokens: int = Field(0, ge=0)  # stable prefix that can be read from the prompt cache
    calls_per_request: float = Field(1.0, ge=0)


class StageSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    p95_ms: float = Field(gt=0)
    p50_ms: Optional[float] = Field(None, gt=0)
    group: Optional[str] = None          # stages with the same group run in parallel


class PathBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    requests_per_day: float = Field(ge=0)
    days: int = 30
    prompt_cache_hit_rate: float = Field(0.0, ge=0, le=1)
    response_cache_hit_rate: float = Field(0.0, ge=0, le=1)
    calls: list[CallSpec] = []
    latency_budget_ms: Optional[float] = None
    stages: list[StageSpec] = []


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixed_monthly_usd: float = 0.0       # hosting, vector DB, tracing plan...
    monthly_limit_usd: Optional[float] = None
    paths: list[PathBudget] = []


class SpecError(ValueError):
    pass


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system: str
    description: str = ""
    boundaries: list[Boundary]
    components: list[Component]
    flows: list[Flow] = []
    budget: Optional[Budget] = None

    @model_validator(mode="after")
    def _references(self):
        seen: set[str] = set()
        for x in [*self.boundaries, *self.components]:
            if x.id in seen:
                raise ValueError(f"duplicate id {x.id!r}")
            seen.add(x.id)
        bids = {b.id for b in self.boundaries}
        cids = {c.id for c in self.components}
        for c in self.components:
            if c.boundary not in bids:
                raise ValueError(f"component {c.id!r}: unknown boundary {c.boundary!r}")
        for f in self.flows:
            for end in (f.src, f.dst):
                if end not in cids:
                    raise ValueError(f"flow {f.key}: unknown component {end!r}")
        return self

    # ------------------------------------------------------------ helpers for rules
    def component(self, cid: str) -> Component:
        for c in self.components:
            if c.id == cid:
                return c
        raise KeyError(cid)

    def has_component(self, cid: str) -> bool:
        return any(c.id == cid for c in self.components)

    def boundary(self, bid: str) -> Boundary:
        for b in self.boundaries:
            if b.id == bid:
                return b
        raise KeyError(bid)

    def trust_of(self, cid: str) -> str:
        """Trust level of the boundary a component lives in."""
        return self.boundary(self.component(cid).boundary).trust

    def outgoing(self, cid: str) -> list[Flow]:
        return [f for f in self.flows if f.src == cid]

    def incoming(self, cid: str) -> list[Flow]:
        return [f for f in self.flows if f.dst == cid]

    def by_kind(self, *kinds: str) -> list[Component]:
        return [c for c in self.components if c.kind in kinds]


def load_spec(source: Union[str, Path, dict]) -> Spec:
    """Load a spec from a YAML path, a YAML string, or a dict. Raises SpecError."""
    if isinstance(source, dict):
        data = source
    else:
        p = Path(source) if not isinstance(source, str) or "\n" not in source else None
        text = p.read_text(encoding="utf-8") if p is not None else source
        data = yaml.safe_load(text)
    try:
        return Spec.model_validate(data)
    except Exception as exc:  # pydantic.ValidationError, but keep callers simple
        raise SpecError(str(exc)) from exc
