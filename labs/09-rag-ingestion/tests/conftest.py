import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(LAB), str(ROOT)]  # so tests can `import mine` and `ragkit`

from ragkit.acme import acme_documents, acme_qa  # noqa: E402
from ragkit.tokens import ApproxTokenizer  # noqa: E402


@pytest.fixture(scope="session")
def tok():
    """Deterministic tokenizer: the same results with or without tiktoken installed."""
    return ApproxTokenizer()


@pytest.fixture(scope="session")
def docs():
    return {d.id: d for d in acme_documents()}


@pytest.fixture(scope="session")
def qa():
    return acme_qa()
