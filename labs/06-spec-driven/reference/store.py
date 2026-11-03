"""In-memory store behind a small interface, so a database can replace it later (spec section 5)."""

from __future__ import annotations

import threading
from typing import Optional


class Store:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}
        self._next = 1
        self._lock = threading.Lock()

    def new_id(self) -> str:
        with self._lock:
            n = self._next
            self._next += 1
        return f"ar_{n:08d}"  # zero-padded, so sorting ids as strings sorts them by creation

    def add(self, item: dict) -> dict:
        with self._lock:
            self._items[item["id"]] = dict(item)
        return dict(item)

    def get(self, request_id: str) -> Optional[dict]:
        item = self._items.get(request_id)
        return dict(item) if item else None

    def update(self, request_id: str, **changes) -> dict:
        with self._lock:
            self._items[request_id].update(changes)
            return dict(self._items[request_id])

    def list(self, status: Optional[str], limit: int) -> tuple[list[dict], int]:
        rows = [r for r in self._items.values() if status is None or r["status"] == status]
        rows.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)  # REQ-6 order and tie-break
        return [dict(r) for r in rows[:limit]], len(rows)
