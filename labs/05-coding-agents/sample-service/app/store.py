"""In-memory storage. Good enough for a demo service; swap for a database later."""

from __future__ import annotations

import itertools
import threading
from datetime import UTC, datetime

from app.models import AccessRequest, AccessRequestIn, Route


class RequestStore:
    def __init__(self) -> None:
        self._items: dict[str, AccessRequest] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def add(self, data: AccessRequestIn, route: Route) -> AccessRequest:
        with self._lock:
            rid = f"req-{next(self._ids):04d}"
            status = "approved" if route == "auto_approve" else "pending"
            item = AccessRequest(
                **data.model_dump(),
                id=rid,
                route=route,
                status=status,
                created_at=datetime.now(UTC),
            )
            self._items[rid] = item
            return item

    def get(self, rid: str) -> AccessRequest | None:
        return self._items.get(rid)

    def list(self, status: str | None = None, route: str | None = None) -> list[AccessRequest]:
        items = list(self._items.values())
        if status:
            items = [i for i in items if i.status == status]
        if route:
            items = [i for i in items if i.route == route]
        return items

    def save(self, item: AccessRequest) -> AccessRequest:
        with self._lock:
            self._items[item.id] = item
            return item

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._ids = itertools.count(1)
