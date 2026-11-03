# Task for a coding agent: SqliteAnswerStore

You are implementing one adapter in an existing ports-and-adapters design.
Read this whole file before writing code.

## Context (read these files, in this order)

1. `designkit/types.py`: the domain types. You need `Answer` (a Pydantic model:
   `model_dump_json()` to serialize, `Answer.model_validate_json(s)` to load).
2. `labs/20-design-driven/mine.py`: the `AnswerStore` port (a `typing.Protocol`)
   and `AnswerStoreContract`, the contract tests every store must pass.
3. `designkit/adapters.py`, class `JsonlAnswerStore`: an existing adapter of the
   same port. Follow its style.

## What to build

A new file `labs/20-design-driven/sqlite_store.py` with one class:

```python
class SqliteAnswerStore:
    def __init__(self, path: str | Path = ":memory:"): ...
    def get(self, request_id: str) -> Answer | None: ...
    def put(self, answer: Answer) -> bool: ...
    def close(self) -> None: ...
```

## The contract (from the port's docstring)

- `get` returns the stored `Answer`, equal to the one that was put, or `None`.
- `put` stores the answer only if no answer with the same `request_id` exists,
  and returns `True`. If one exists it returns `False` and does NOT overwrite
  it: first write wins. This must hold even if two threads call `put` with the
  same id at the same time, so enforce it in the database (a primary key),
  not with a check-then-insert in Python.
- Data survives closing and reopening the same file.

## Constraints

- Standard library only (`sqlite3`). No ORM, no new dependency.
- Do not change `mine.py`, `designkit/`, or anything under `tests/`.
- Do not make the class inherit from the Protocol: structural typing is the point.

## Done when

```bash
python -m pytest -q labs/20-design-driven/tests/test_ex5_agent_adapter.py
```

passes, and you have shown the test output. If a test fails, fix the adapter, not the test.
