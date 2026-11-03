"""Exercise 5: the SqliteAnswerStore that a coding agent writes from designs/adapter_task.md.
It must pass YOUR AnswerStoreContract (exercise 4) plus one persistence test."""

import importlib
from datetime import datetime, timezone

import pytest

import mine
from designkit.types import Answer

try:
    sqlite_store = importlib.import_module("sqlite_store")
except ModuleNotFoundError:
    sqlite_store = None


def _require():
    if sqlite_store is None:
        pytest.fail("exercise 5: labs/20-design-driven/sqlite_store.py does not exist yet. "
                    "Give designs/adapter_task.md to your coding agent.", pytrace=False)
    return sqlite_store.SqliteAnswerStore


class TestSqliteAnswerStore(mine.AnswerStoreContract):
    def make_store(self):
        return _require()(":memory:")


def test_is_an_answer_store():
    assert isinstance(_require()(":memory:"), mine.AnswerStore)


def test_survives_reopening_the_file(tmp_path):
    Store = _require()
    path = tmp_path / "answers.db"
    a = Answer(request_id="r1", status="answered", text="kept", citations=["vacation_policy.md"],
               created_at=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc))
    s1 = Store(path)
    assert s1.put(a) is True
    if hasattr(s1, "close"):
        s1.close()
    s2 = Store(path)
    assert s2.get("r1") == a
    assert s2.put(a.model_copy(update={"text": "other"})) is False
