import json
import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(LAB), str(ROOT)]  # so tests can `import mine` and `ragkit`

FIXTURES = LAB / "fixtures"


@pytest.fixture(scope="session")
def cases():
    """The constructed cases of fixtures/cases.jsonl: [(name, expected_stage, Case, why)]."""
    from ragkit.diagnose import Case
    rows = [json.loads(x) for x in (FIXTURES / "cases.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return [(r["name"], r["expected"], Case(**r["case"]), r["why"]) for r in rows]


@pytest.fixture(scope="session")
def claim_examples():
    return [json.loads(x) for x in (FIXTURES / "claims_examples.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip()]
