import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB))  # so tests can `import mine`
sys.path.insert(0, str(LAB.parent.parent))  # and servekit / mockllm from the repo root

from mockllm import MockConfig  # noqa: E402
from servekit.mock import long_reply, start_counting_in_thread  # noqa: E402


@pytest.fixture(scope="session")
def _server():
    server, url = start_counting_in_thread(MockConfig())
    yield server, url
    server.shutdown()


@pytest.fixture
def mock(_server):
    """A fresh, instant mock LLM (counting variant). Returns (server, url)."""
    server, url = _server
    server.state.cfg = MockConfig(ttft=0, tps=0, seed=1, reply=long_reply(12))
    server.state.reset()
    server.counters.reset()
    return server, url
