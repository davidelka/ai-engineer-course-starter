"""Reference SqliteAnswerStore: what the coding agent should produce in exercise 5.
stdlib sqlite3, first write wins through the PRIMARY KEY and INSERT OR IGNORE."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional, Union

from .types import Answer


class SqliteAnswerStore:
    def __init__(self, path: Union[str, Path] = ":memory:"):
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._conn:
            self._conn.execute("CREATE TABLE IF NOT EXISTS answers (request_id TEXT PRIMARY KEY, body TEXT NOT NULL)")

    def get(self, request_id: str) -> Optional[Answer]:
        with self._lock:
            row = self._conn.execute("SELECT body FROM answers WHERE request_id = ?", (request_id,)).fetchone()
        return Answer.model_validate_json(row[0]) if row else None

    def put(self, answer: Answer) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute("INSERT OR IGNORE INTO answers (request_id, body) VALUES (?, ?)",
                                     (answer.request_id, answer.model_dump_json()))
        return cur.rowcount == 1

    def close(self) -> None:
        self._conn.close()
