import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(LAB), str(ROOT)]  # so tests can `import mine`, `ctxkit`, `llmkit`

from mockllm import MockConfig, start_in_thread  # noqa: E402


def words(text: str) -> int:
    """The token counter the tests use: whitespace-separated words."""
    return len(text.split())


@pytest.fixture(scope="session")
def _server():
    server, url = start_in_thread(MockConfig())
    yield server, url
    server.shutdown()


@pytest.fixture
def mock(_server):
    server, url = _server
    server.state.cfg = MockConfig(ttft=0, tps=0, seed=1)
    server.state.reset()
    return server, url
