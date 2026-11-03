"""Gateway configuration (YAML), shaped on purpose like LiteLLM's config.yaml.

    model_list:
      - model_name: haiku                 # what clients send as "model"
        deployments:                      # tried in this order (fallback chain)
          - id: anthropic-us
            model: anthropic:claude-haiku-5-5   # an llmkit spec
            region: us
            api_key_env: ANTHROPIC_API_KEY      # or api_key: mock-key (mock servers only)
            base_url: http://127.0.0.1:8765     # optional: mock server, proxy, private endpoint
            prices: {input: 0.10, output: 0.50} # optional: USD per 1M tokens, overrides llmkit
    router: {retries_per_deployment: 1, failure_threshold: 3, cooldown_s: 30}
    cache: {enabled: false, ttl_s: 300}
    audit: {path: state/audit.jsonl, log_content: none, retention_days: 365}
    restore_pii_in_response: true
    rpm_default: 0
    policy: policy.yaml
    keys: state/keys.yaml
    master_key_env: GATEWAY_MASTER_KEY

Relative paths are relative to the config file. Every deployment must have a price
(llmkit's table or `prices:`): the gateway refuses to start otherwise, because a
model without a price would be free and bypass every budget.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import yaml

from llmkit.client import parse_spec
from llmkit.pricing import PRICES


@dataclass
class Deployment:
    id: str
    model_spec: str  # llmkit spec, e.g. "anthropic:claude-haiku-5-5"
    region: str = "us"
    base_url: Optional[str] = None
    api_key: Optional[str] = None  # literal, for mock servers only
    api_key_env: Optional[str] = None
    prices: Optional[dict] = None

    @property
    def provider(self) -> str:
        return parse_spec(self.model_spec)[0]

    @property
    def model(self) -> str:
        return parse_spec(self.model_spec)[1]

    def resolve_key(self) -> str:
        if self.api_key_env:
            value = os.environ.get(self.api_key_env)
            if not value:
                raise ValueError(f"deployment {self.id}: environment variable {self.api_key_env} is not set")
            return value
        if self.api_key:
            return self.api_key
        raise ValueError(f"deployment {self.id}: set api_key_env (real providers) or api_key (mock servers)")


@dataclass
class ModelGroup:
    name: str
    deployments: list[Deployment]


@dataclass
class GatewayConfig:
    models: dict[str, ModelGroup]
    retries_per_deployment: int = 1
    failure_threshold: int = 3
    cooldown_s: float = 30.0
    cache_enabled: bool = False
    cache_ttl_s: float = 300.0
    audit_path: Optional[Path] = None
    log_content: str = "none"  # none | redacted
    retention_days: int = 365
    restore_pii_in_response: bool = True
    rpm_default: int = 0
    policy_path: Optional[Path] = None
    keys_path: Optional[Path] = None
    master_key_env: str = "GATEWAY_MASTER_KEY"
    pii_salt_env: str = "GATEWAY_PII_SALT"
    base_dir: Path = field(default_factory=Path.cwd)

    def price_table(self) -> dict:
        """llmkit's prices, overridden by per-deployment `prices:`."""
        table = dict(PRICES)
        for group in self.models.values():
            for d in group.deployments:
                if d.prices:
                    table[d.model] = {**table.get(d.model, {}), **d.prices}
        return table

    def deployment(self, dep_id: str) -> Deployment:
        for group in self.models.values():
            for d in group.deployments:
                if d.id == dep_id:
                    return d
        raise KeyError(dep_id)


def _path(base: Path, value: Optional[str]) -> Optional[Path]:
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else base / p


def parse_config(data: dict, base_dir: Union[str, Path] = ".") -> GatewayConfig:
    base = Path(base_dir)
    models: dict[str, ModelGroup] = {}
    seen: set[str] = set()
    for entry in data.get("model_list") or []:
        name = entry["model_name"]
        deps = []
        for d in entry.get("deployments") or []:
            dep = Deployment(id=d["id"], model_spec=d["model"], region=d.get("region", "us"),
                             base_url=d.get("base_url"), api_key=d.get("api_key"),
                             api_key_env=d.get("api_key_env"), prices=d.get("prices"))
            parse_spec(dep.model_spec)  # fail fast on a bad spec
            if dep.id in seen:
                raise ValueError(f"deployment id {dep.id!r} is used twice")
            seen.add(dep.id)
            deps.append(dep)
        if not deps:
            raise ValueError(f"model {name!r} has no deployments")
        models[name] = ModelGroup(name, deps)
    if not models:
        raise ValueError("config has an empty model_list")
    router = data.get("router") or {}
    cache = data.get("cache") or {}
    audit = data.get("audit") or {}
    cfg = GatewayConfig(
        models=models,
        retries_per_deployment=int(router.get("retries_per_deployment", 1)),
        failure_threshold=int(router.get("failure_threshold", 3)),
        cooldown_s=float(router.get("cooldown_s", 30.0)),
        cache_enabled=bool(cache.get("enabled", False)),
        cache_ttl_s=float(cache.get("ttl_s", 300.0)),
        audit_path=_path(base, audit.get("path")),
        log_content=audit.get("log_content", "none"),
        retention_days=int(audit.get("retention_days", 365)),
        restore_pii_in_response=bool(data.get("restore_pii_in_response", True)),
        rpm_default=int(data.get("rpm_default", 0)),
        policy_path=_path(base, data.get("policy")),
        keys_path=_path(base, data.get("keys")),
        master_key_env=data.get("master_key_env", "GATEWAY_MASTER_KEY"),
        base_dir=base,
    )
    if cfg.log_content not in ("none", "redacted"):
        raise ValueError("audit.log_content must be 'none' or 'redacted' (never the raw prompt)")
    prices = cfg.price_table()
    for group in models.values():
        for d in group.deployments:
            p = prices.get(d.model)
            if not p or "input" not in p or "output" not in p:
                raise ValueError(f"deployment {d.id}: no price for model {d.model!r}. Add `prices: "
                                 "{input: ..., output: ...}` (USD per 1M tokens): an unpriced model "
                                 "would be free and bypass every budget")
    return cfg


def load_config(path: Union[str, Path]) -> GatewayConfig:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return parse_config(data, p.resolve().parent)
