"""Virtual keys: what each app gets instead of the real provider key.

The store keeps only a SHA-256 of each key. The raw key is shown once, when it is
created, exactly like LiteLLM ("Copy the key now; it is shown only once"), GitHub
tokens and cloud access keys. A leaked keys.yaml therefore reveals who has access to
what, but no usable key.

The "sk-gw-" prefix is not decoration: a fixed, distinctive prefix lets secret
scanners (GitHub secret scanning custom patterns, gitleaks, trufflehog) find a key
that was pasted into a repo, a ticket or a Slack message.

    python -m gatewaykit.keys new --store state/keys.yaml --id support-bot --team support --models haiku
    python -m gatewaykit.keys revoke --store state/keys.yaml --id support-bot
    python -m gatewaykit.keys list --store state/keys.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import secrets
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Union

import yaml

PREFIX = "sk-gw-"


def generate_key() -> str:
    return PREFIX + secrets.token_urlsafe(24)


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class VirtualKey:
    key_id: str  # a name for humans and logs; never the key itself
    sha256: str
    team: str
    owner: str = ""
    models: list[str] = field(default_factory=list)  # empty = every model
    max_budget_usd: Optional[float] = None
    soft_budget_usd: Optional[float] = None
    budget_period_days: Optional[float] = None
    rpm_limit: int = 0  # 0 = no limit
    classification_floor: Optional[str] = None  # the minimum classification of this app's traffic
    revoked: bool = False

    @property
    def hint(self) -> str:
        """Safe to log: the id and the last 4 hex chars of the hash."""
        return f"{self.key_id}(...{self.sha256[-4:]})"


class KeyStore:
    def __init__(self, keys: Optional[list[VirtualKey]] = None, path: Optional[Path] = None):
        self.path = Path(path) if path else None
        self._by_hash = {k.sha256: k for k in keys or []}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ persistence
    @classmethod
    def load(cls, path: Union[str, Path]) -> "KeyStore":
        p = Path(path)
        if not p.exists():
            return cls([], p)
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls([VirtualKey(**k) for k in data.get("keys") or []], p)

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"keys": [asdict(k) for k in sorted(self._by_hash.values(), key=lambda k: k.key_id)]}
        self.path.write_text("# Hashes only. Raw keys are shown once, at creation.\n"
                             + yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    # ------------------------------------------------------------ operations
    def lookup(self, raw: Optional[str]) -> Optional[VirtualKey]:
        if not raw:
            return None
        return self._by_hash.get(hash_key(raw))

    def by_id(self, key_id: str) -> Optional[VirtualKey]:
        return next((k for k in self._by_hash.values() if k.key_id == key_id), None)

    def all(self) -> list[VirtualKey]:
        return sorted(self._by_hash.values(), key=lambda k: k.key_id)

    def create(self, key_id: str, team: str, raw: Optional[str] = None, **fields) -> tuple[str, VirtualKey]:
        """Returns (raw_key, record). The raw key is not stored anywhere."""
        with self._lock:
            if self.by_id(key_id):
                raise ValueError(f"key id {key_id!r} already exists")
            raw = raw or generate_key()
            vk = VirtualKey(key_id=key_id, sha256=hash_key(raw), team=team, **fields)
            self._by_hash[vk.sha256] = vk
            self.save()
            return raw, vk

    def revoke(self, key_id: str) -> VirtualKey:
        with self._lock:
            vk = self.by_id(key_id)
            if not vk:
                raise KeyError(key_id)
            vk.revoked = True
            self.save()
            return vk


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m gatewaykit.keys")
    p.add_argument("action", choices=["new", "revoke", "list"])
    p.add_argument("--store", required=True)
    p.add_argument("--id")
    p.add_argument("--team", default="default")
    p.add_argument("--owner", default="")
    p.add_argument("--models", default="", help="comma separated; empty = all")
    p.add_argument("--budget", type=float, default=None, help="hard budget, USD")
    p.add_argument("--soft", type=float, default=None, help="soft budget, USD")
    p.add_argument("--period-days", type=float, default=None)
    p.add_argument("--rpm", type=int, default=0)
    p.add_argument("--floor", default=None, help="minimum data classification")
    a = p.parse_args()
    store = KeyStore.load(a.store)
    if a.action == "list":
        for k in store.all():
            print(f"{k.key_id:18} team={k.team:12} models={','.join(k.models) or '*':20} "
                  f"budget={k.max_budget_usd} revoked={k.revoked} hash=...{k.sha256[-4:]}")
    elif a.action == "new":
        raw, vk = store.create(a.id, a.team, owner=a.owner,
                               models=[m for m in a.models.split(",") if m],
                               max_budget_usd=a.budget, soft_budget_usd=a.soft,
                               budget_period_days=a.period_days, rpm_limit=a.rpm,
                               classification_floor=a.floor)
        print(f"created {vk.key_id}. The key is shown ONCE, store it now:\n{raw}")
    else:
        vk = store.revoke(a.id)
        print(f"revoked {vk.hint}. A running gateway picks this up via POST /admin/keys/{vk.key_id}/revoke "
              "or a restart.")


if __name__ == "__main__":
    main()
