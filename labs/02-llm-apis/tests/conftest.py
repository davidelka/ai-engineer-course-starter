import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB))  # so tests can `import mine`

from mockllm import MockConfig, start_in_thread  # noqa: E402


@pytest.fixture(scope="session")
def _server():
    server, url = start_in_thread(MockConfig())
    yield server, url
    server.shutdown()


@pytest.fixture
def mock(_server):
    server, url = _server
    server.state.cfg = MockConfig(ttft=0, tps=0, seed=1)
    server.state.rng.seed(1)
    server.state.reset()
    return server, url
