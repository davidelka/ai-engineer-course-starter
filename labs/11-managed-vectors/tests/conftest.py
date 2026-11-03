import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(LAB), str(ROOT)]  # so tests can `import mine` and `ragkit`


@pytest.fixture(scope="session")
def chunks():
    """The Acme chunks the lab scripts use (lesson 9's baseline chunker)."""
    from ragkit.acme import acme_chunks
    from ragkit.chunking import make_chunker
    return acme_chunks(make_chunker("heading:400:40:150", "approx"))
