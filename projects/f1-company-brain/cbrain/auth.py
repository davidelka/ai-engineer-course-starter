"""Users, roles and API keys: one identity for the HTTP API, the UI and the MCP server.

Four roles, and what each one is FOR (not what each one may decide):
    employee   ask questions, file access requests, see their own requests
    manager    + the approvals tab (requests of their direct reports)
    security   + the approvals tab for every needs_security request, and every request's audit
    admin      operations: every request and audit, metrics. NOT an approver: an admin who is not in
               Acme's directory can never decide a request, because flowkit checks the directory.

The role gives access to an endpoint; the directory gives authority over a specific request. Two
checks, two owners: a stolen manager key still cannot approve someone else's report.

Keys
    BRAIN_API_KEYS='{"dana": "<key>", ...}'   one JSON secret (Secrets Manager in AWS, .env locally).
    Only sha256 hashes are kept in memory; comparison with hmac.compare_digest.
    BRAIN_DEMO_KEYS=1 also accepts "demo-<user_id>" (the UI's user picker). Local demos only:
    the production compose file and the Terraform never set it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

ROLES = ("employee", "manager", "security", "admin")


@dataclass(frozen=True)
class Principal:
    id: str
    email: str
    name: str
    employee_id: Optional[str]
    roles: frozenset = field(default_factory=frozenset)
    acl_role: str = "employee"           # acmeqa / ragkit document role

    def has(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    @property
    def is_security(self) -> bool:
        return "security" in self.roles

    def public(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "employee_id": self.employee_id,
                "roles": sorted(self.roles), "acl_role": self.acl_role}


def load_users(path: Path) -> dict[str, Principal]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for u in data["users"]:
        bad = set(u["roles"]) - set(ROLES)
        if bad:
            raise ValueError(f"user {u['id']}: unknown roles {sorted(bad)}")
        out[u["id"]] = Principal(id=u["id"], email=u["email"], name=u["name"], employee_id=u.get("employee_id"),
                                 roles=frozenset(u["roles"]), acl_role=u.get("acl_role", "employee"))
    return out


def _h(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class KeyRing:
    """API key -> Principal. Holds hashes only."""

    def __init__(self, users: dict[str, Principal], keys: Optional[dict[str, str]] = None, *, demo: bool = False):
        self.users = users
        self._hashes: list[tuple[str, str]] = []          # (sha256(key), user_id)
        for uid, key in (keys or {}).items():
            if uid not in users:
                raise ValueError(f"BRAIN_API_KEYS names an unknown user {uid!r}")
            if len(key) < 16:
                raise ValueError(f"the key of {uid!r} is too short (min 16 characters)")
            self._hashes.append((_h(key), uid))
        if demo:
            self._hashes += [(_h(f"demo-{uid}"), uid) for uid in users]
        self.demo = demo

    @classmethod
    def from_env(cls, users: dict[str, Principal], *, demo: bool = False) -> "KeyRing":
        raw = os.environ.get("BRAIN_API_KEYS", "").strip()
        keys = json.loads(raw) if raw else {}
        return cls(users, keys, demo=demo)

    def lookup(self, presented: Optional[str]) -> Optional[Principal]:
        if not presented:
            return None
        h = _h(presented.strip())
        found = None
        for known, uid in self._hashes:      # no early exit: same work for every key
            if hmac.compare_digest(known, h):
                found = uid
        return self.users.get(found) if found else None

    def __len__(self) -> int:
        return len(self._hashes)


def presented_key(headers: dict) -> Optional[str]:
    """Authorization: Bearer <key>, or X-API-Key: <key>."""
    h = {k.lower(): v for k, v in headers.items()}
    auth = h.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return h.get("x-api-key") or None


def require(p: Optional[Principal], roles: Iterable[str] = ()) -> Principal:
    """Raise PermissionError unless p exists and has one of roles (empty = any authenticated user)."""
    if p is None:
        raise PermissionError("unauthenticated")
    roles = tuple(roles)
    if roles and not p.has(*roles):
        raise PermissionError(f"needs one of the roles {', '.join(roles)}")
    return p
