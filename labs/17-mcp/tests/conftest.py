import asyncio
import random
import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB))  # so tests can `import mine` and `import evil_server`
sys.path.insert(0, str(LAB.parents[1]))

from llmkit import LLM, RetryPolicy  # noqa: E402
from mockllm import MockConfig, start_in_thread  # noqa: E402
from toolkit import acme_registry  # noqa: E402


def run(coro):
    """Run one coroutine (the MCP SDK is async; the tests stay plain functions)."""
    return asyncio.run(coro)


@pytest.fixture
def reg(tmp_path):
    return acme_registry(requests_db=tmp_path / "requests.db")


@pytest.fixture(scope="session")
def _mock():
    server, url = start_in_thread(MockConfig())
    yield server, url
    server.shutdown()


@pytest.fixture
def mock(_mock):
    server, url = _mock
    server.state.cfg = MockConfig(ttft=0, tps=0, seed=1)
    server.state.rng.seed(1)
    server.state.reset()
    return server, url


@pytest.fixture
def make_llm():
    def make(url, provider="anthropic"):
        return LLM(f"{provider}:mock-model", api_key="t", base_url=url,
                   retry=RetryPolicy(sleep=lambda s: None, rng=random.Random(0)))
    return make
