import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(LAB), str(ROOT)]  # so tests can `import mine`, `evalkit` and `ragkit`


@pytest.fixture(scope="session")
def golden():
    from evalkit import acme_golden
    return acme_golden()


@pytest.fixture(scope="session")
def baseline_outputs(golden):
    """The extractive baseline's outputs on all 79 questions (free, about a second)."""
    from _lab import build_index, system_for
    from evalkit import run_system
    return run_system(system_for("extractive", "v1", 5, index=build_index()), golden)
