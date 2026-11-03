"""Exercise 4: exponential backoff with full jitter, plus a run against a flaky server."""

import random
import statistics

from llmkit import LLM, RetryPolicy
from mine import backoff_delay


def test_stays_within_the_exponential_envelope():
    rng = random.Random(1)
    for attempt in range(10):
        for _ in range(50):
            d = backoff_delay(attempt, base=0.5, cap=8, rng=rng)
            assert 0 <= d <= min(8, 0.5 * 2**attempt) + 1e-9


def test_it_is_random_not_fixed():
    rng = random.Random(2)
    samples = [backoff_delay(3, base=0.5, cap=20, rng=rng) for _ in range(200)]
    assert len(set(samples)) > 150, "full jitter: values should differ"
    assert 1.5 < statistics.mean(samples) < 2.5, "uniform(0, 4) has mean 2"


def test_grows_with_attempts_on_average():
    rng = random.Random(3)
    mean = lambda a: statistics.mean(backoff_delay(a, base=0.5, cap=100, rng=rng) for _ in range(300))  # noqa: E731
    assert mean(0) < mean(2) < mean(4)


def test_cap_is_respected():
    rng = random.Random(4)
    assert max(backoff_delay(30, base=0.5, cap=3, rng=rng) for _ in range(200)) <= 3


def test_retry_after_is_a_floor():
    rng = random.Random(5)
    assert all(backoff_delay(0, retry_after=6, rng=rng) >= 6 for _ in range(50))


def test_your_policy_survives_a_flaky_server(mock):
    """40% of requests fail with 529. With 4 attempts, ~97% of calls should succeed."""
    from mine import classify_error

    server, url = mock
    server.state.cfg.fail_rate = 0.4
    sleeps = []
    policy = RetryPolicy(max_attempts=4, classify=classify_error, delay=backoff_delay,
                         sleep=sleeps.append, rng=random.Random(0))
    llm = LLM("anthropic:mock-model", api_key="t", base_url=url, retry=policy)
    ok = 0
    for _ in range(60):
        try:
            r = llm.complete("hi")
            assert r.attempts <= 4
            ok += 1
        except Exception:
            pass
    assert ok >= 54, f"only {ok}/60 succeeded"
    assert sleeps and max(sleeps) <= policy.cap
