import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB))  # so tests can `import mine` and `import make_day`

from obskit import load_spans  # noqa: E402


@pytest.fixture(scope="session")
def forensic():
    """The 12 recorded traces of exercise 5 (48 spans)."""
    return load_spans(LAB / "fixtures" / "forensic.jsonl")


def mk(trace, sid, name, start, dur, parent=None, status="OK", **attrs):
    """A hand-made span dict, for small exact tests."""
    return {"trace_id": trace, "span_id": sid, "parent_id": parent, "name": name, "kind": "INTERNAL",
            "start_ms": float(start), "end_ms": float(start + dur), "duration_ms": float(dur),
            "status": status, "status_message": "", "attributes": dict(attrs), "events": [], "links": []}
