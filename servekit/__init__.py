"""servekit: serving LLM features as a production API (lesson 26).

    python -m servekit.mock            # mockllm + stream counters, port 8765
    python -m servekit                 # Company Brain API v0 on port 8000

Modules:
    app          FastAPI app factory: /v1/answer, /v1/answer/stream, health, stats
    async_llm    AsyncLLM (httpx.AsyncClient over llmkit's adapters), threaded_stream, leaky_stream
    ratelimit    TokenBucket, KeyedRateLimiter, RateLimit headers
    gate         ConcurrencyGate: semaphore + bounded queue + queue timeout -> 429
    idempotency  Idempotency-Key store (IETF draft semantics)
    problems     application/problem+json error contract (RFC 9457)
    logs         request ids and JSON logs (pure ASGI middleware)
    brain        Company Brain v0: keyword retrieval over Acme docs + prompt
    mock         mockllm subclass that counts completed vs aborted streams
    loadtest     locust CSV parsing, knee detection, chart
"""

from .gate import ConcurrencyGate, GateRejected
from .idempotency import IdempotencyStore, fingerprint
from .problems import Problem
from .ratelimit import KeyedRateLimiter, TokenBucket

__all__ = ["ConcurrencyGate", "GateRejected", "IdempotencyStore", "fingerprint", "Problem",
           "KeyedRateLimiter", "TokenBucket"]
