"""Reference ACL rules for retrieval (lesson 24, exercise 5).

The rule that matters most is WHERE the filter runs: before ranking, on the candidate set,
in code, from the authenticated user's role. Never "tell the model not to reveal
confidential documents", and never filter after taking the top k (that both leaks
through the ranking and silently returns fewer results).

Matrix (classification x role):
  public        every role, including contractor
  internal      every role except contractor
  confidential  security, or a role whose department equals the document's department
                (engineering -> engineering, support -> sales_support, hr -> hr)
  anything else (restricted, missing, misspelled, unknown role) -> denied: fail closed
"""

from __future__ import annotations

from typing import Iterable

from .types import ROLE_DEPARTMENT, ROLES, Chunk, User


def acl_allows(role: str, meta: dict) -> bool:
    if role not in ROLES:
        return False
    cls = str(meta.get("classification") or "").strip().lower()
    if cls == "public":
        return True
    if cls == "internal":
        return role != "contractor"
    if cls == "confidential":
        return role == "security" or (
            ROLE_DEPARTMENT.get(role) is not None and ROLE_DEPARTMENT.get(role) == meta.get("department"))
    return False


def acl_filter(user: User, chunks: Iterable[Chunk]) -> list[Chunk]:
    return [c for c in chunks if acl_allows(user.role, c.meta)]
