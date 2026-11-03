"""Small data types shared by every guardkit module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Roles in the ACL exercise, and the department each role belongs to. A role without a
# department (contractor, employee) never sees confidential documents.
ROLES = ("contractor", "employee", "support", "engineering", "security", "hr")
ROLE_DEPARTMENT = {
    "support": "sales_support",
    "engineering": "engineering",
    "hr": "hr",
    "security": "it_security",
}


@dataclass(frozen=True)
class User:
    id: str
    role: str
    email: str = ""


@dataclass
class Chunk:
    """One retrievable piece of a document. `meta` carries classification, department,
    origin (acme / partner / web / email / tool) and title."""

    id: str
    doc_id: str
    text: str
    meta: dict = field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.meta.get("title", self.doc_id)

    @property
    def classification(self) -> Optional[str]:
        return self.meta.get("classification")


@dataclass(frozen=True)
class Finding:
    """One problem an output check found. kind is a short machine name, detail is for humans."""

    kind: str
    detail: str = ""


@dataclass
class Action:
    """A side effect the model asked for, e.g. ACTION: send_email {"to": ...}."""

    name: str
    args: dict
    status: str = "executed"  # executed | dropped_not_allowed | pending_confirmation


@dataclass
class Trace:
    """Everything that happened to one request. The evaluator and the --show views read it."""

    question: str
    user: User
    system: str = ""
    prompt: str = ""
    retrieved: list[Chunk] = field(default_factory=list)
    dropped: list[tuple[str, str]] = field(default_factory=list)  # (chunk id or "tool", reason)
    acl_removed: list[str] = field(default_factory=list)  # chunk ids hidden by the ACL
    raw_output: str = ""
    output: str = ""  # what the user finally sees
    actions: list[Action] = field(default_factory=list)
    blocked_by: Optional[str] = None  # layer name that blocked or replaced the answer
    block_reason: str = ""
    findings: list[Finding] = field(default_factory=list)
    events: list[str] = field(default_factory=list)  # human-readable log of every layer decision
    cost_usd: float = 0.0
    calls: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def executed_actions(self) -> list[Action]:
        return [a for a in self.actions if a.status == "executed"]
