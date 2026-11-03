"""llmkit against the local mock server: every provider, every fault. Offline and free."""

import random

import httpx
import pytest

from llmkit import LLM, ChatRequest, LLMError, Message, RetryPolicy, backoff_delay, classify_error, cost_usd
from llmkit.sse import iter_sse
from llmkit.types import Usage
from mockllm import MockConfig, start_in_thread

PROVIDERS = ["anthropic", "openai", "gemini"]


@pytest.fixture(scope="module")
def _server():
    server, url = start_in_thread(MockConfig())
    yield server, url
    server.shutdown()


@pytest.fixture
def mock(_server):
    """One server per module (start/stop is slow); fresh faults and counters per test."""
    server, url = _server
    server.state.cfg = MockConfig(ttft=0, tps=0, seed=1)
    server.state.rng.seed(1)
    server.state.reset()
    return server, url


def client(url, provider="anthropic", **kw):
    sleeps = []
    policy = RetryPolicy(sleep=sleeps.append, rng=random.Random(0), **kw)
    llm = LLM(f"{provider}:mock-model", api_key="test", base_url=url, retry=policy)
    llm.sleeps = sleeps
    return llm


def configure(server, **kw):
    for k, v in kw.items():
        setattr(server.state.cfg, k, v)


# ---------------------------------------------------------------- happy path
@pytest.mark.parametrize("provider", PROVIDERS)
def test_complete_normalizes_every_provider(mock, provider):
    server, url = mock
    r = client(url, provider).complete("Name two colors.", system="Be brief.", max_tokens=200)
    assert "Name two colors." in r.text
    assert r.stop_reason == "end"
    assert r.usage.input_tokens > 0 and r.usage.output_tokens > 0
    assert r.cost_usd is not None and r.cost_usd > 0
    assert r.attempts == 1


@pytest.mark.parametrize("provider", PROVIDERS)
def test_stream_yields_text_then_done(mock, provider):
    server, url = mock
    events = list(client(url, provider).stream("Tell me something"))
    texts = [e.text for e in events if e.type == "text"]
    assert len(texts) > 3
    assert events[-1].type == "done"
    result = events[-1].result
    assert result.text == "".join(texts)
    assert result.ttft_s is not None and result.usage.output_tokens > 0


@pytest.mark.parametrize("provider", PROVIDERS)
def test_max_tokens_is_normalized(mock, provider):
    server, url = mock
    r = client(url, provider).complete("a question that needs a long answer", max_tokens=3)
    assert r.stop_reason == "max_tokens"


def test_conversation_history_is_sent(mock):
    server, url = mock
    req = ChatRequest(messages=[Message("user", "Q1"), Message("assistant", "A1"), Message("user", "And Q2?")])
    for provider in PROVIDERS:
        assert "And Q2?" in client(url, provider).complete(req).text


# ---------------------------------------------------------------- errors and retries
def test_retryable_error_is_retried(mock):
    server, url = mock
    configure(server, fail_first=2, status=529)
    llm = client(url)
    r = llm.complete("hi")
    assert r.attempts == 3 and len(llm.sleeps) == 2
    assert server.state.requests == 3


def test_client_error_is_not_retried(mock):
    server, url = mock
    configure(server, fail_first=5, status=400)
    llm = client(url)
    with pytest.raises(LLMError) as exc:
        llm.complete("hi")
    assert exc.value.status == 400 and exc.value.kind == "invalid_request_error"
    assert server.state.requests == 1 and llm.sleeps == []


def test_gives_up_after_max_attempts(mock):
    server, url = mock
    configure(server, fail_first=100, status=500)
    with pytest.raises(LLMError):
        client(url, max_attempts=4).complete("hi")
    assert server.state.requests == 4


def test_retry_after_is_respected(mock):
    server, url = mock
    configure(server, fail_first=1, status=429, retry_after=7)
    llm = client(url)
    llm.complete("hi")
    assert llm.sleeps[0] >= 7


def test_request_id_is_captured_on_errors(mock):
    server, url = mock
    configure(server, fail_first=5, status=401)
    with pytest.raises(LLMError) as exc:
        client(url).complete("hi")
    assert exc.value.request_id and exc.value.request_id.startswith("req_mock_")


def test_malformed_json_is_retried(mock):
    server, url = mock
    configure(server, malformed_rate=1.0)
    with pytest.raises(LLMError) as exc:
        client(url, max_attempts=2).complete("hi")
    assert exc.value.kind == "malformed_response" and server.state.requests == 2


def test_timeout_becomes_llm_error(mock):
    server, url = mock
    configure(server, latency=0.5)
    llm = LLM("anthropic:mock-model", api_key="t", base_url=url, retry=RetryPolicy.none(),
              timeout=httpx.Timeout(0.1))
    with pytest.raises(LLMError) as exc:
        llm.complete("hi")
    assert exc.value.kind == "timeout"


def test_lesson1_temperature_error_reproduced(mock):
    server, url = mock
    llm = client(url)
    req = ChatRequest.from_prompt("hi", extra_body={"temperature": 0.2})
    llm.complete(req)  # pinned 2023-06-01: accepted
    import llmkit.providers.anthropic as a
    old, a.API_VERSION = a.API_VERSION, "2026-10-21"
    try:
        with pytest.raises(LLMError, match="Extra inputs are not permitted"):
            llm.complete(req)
    finally:
        a.API_VERSION = old


# ---------------------------------------------------------------- streaming faults
@pytest.mark.parametrize("provider", PROVIDERS)
def test_truncated_stream_after_text_raises_with_partial(mock, provider):
    server, url = mock
    configure(server, truncate_after=3)
    with pytest.raises(LLMError) as exc:
        for _ in client(url, provider).stream("Tell me a long story please"):
            pass
    assert exc.value.kind == "stream_truncated"
    assert exc.value.partial_text  # what the user already saw
    assert server.state.requests == 1  # no silent restart after text was shown


@pytest.mark.parametrize("provider", PROVIDERS)
def test_in_stream_error_after_200(mock, provider):
    server, url = mock
    configure(server, error_after=2)
    with pytest.raises(LLMError) as exc:
        list(client(url, provider).stream("Tell me a long story please"))
    assert exc.value.partial_text


def test_collected_stream_retries_from_scratch(mock):
    server, url = mock
    configure(server, truncate_after=2)
    llm = client(url, max_attempts=3)
    with pytest.raises(LLMError):
        llm.complete("story", stream=True)
    assert server.state.requests == 3  # nothing was shown, so a full retry is safe
    configure(server, truncate_after=0)
    assert llm.complete("story", stream=True).ttft_s is not None


def test_stream_retries_before_first_token(mock):
    server, url = mock
    configure(server, fail_first=1, status=529)
    llm = client(url)
    events = list(llm.stream("hi"))
    assert events[-1].result.attempts == 2


# ---------------------------------------------------------------- pieces
def test_sse_parser():
    lines = ["event: a", "data: {\"x\": 1}", "", ": keep-alive", "data: line1", "data: line2", ""]
    evs = list(iter_sse(lines))
    assert [(e.event, e.data) for e in evs] == [("a", '{"x": 1}'), (None, "line1\nline2")]


def test_backoff_reference_bounds():
    rng = random.Random(3)
    for attempt in range(8):
        d = backoff_delay(attempt, base=0.5, cap=4, rng=rng)
        assert 0 <= d <= min(4, 0.5 * 2**attempt)
    assert backoff_delay(0, retry_after=9, rng=rng) >= 9


def test_classify_reference():
    assert classify_error(LLMError("x", status=529)).retry
    assert not classify_error(LLMError("x", status=400)).retry
    assert classify_error(LLMError("x", kind="timeout")).retry


def test_cost_counts_thinking_as_output_and_long_context_tier():
    u = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost_usd("claude-haiku-5-5", u) == pytest.approx(0.60 * 5)  # above 100K: x5
    assert cost_usd("claude-haiku-5-5", Usage(input_tokens=10_000, output_tokens=0)) == pytest.approx(0.001)
    assert cost_usd("unknown-model", u) is None


def test_tokens_per_second_excludes_thinking():
    from llmkit.types import ChatResult
    r = ChatResult(text="x", stop_reason="end", provider="p", model="m", latency_s=3.0, ttft_s=2.0,
                   usage=Usage(input_tokens=10, output_tokens=300, thinking_tokens=250))
    assert r.tokens_per_second == pytest.approx(50)  # 50 visible tokens in 1 second, not 300
