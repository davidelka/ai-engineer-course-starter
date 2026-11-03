"""Run Company Brain API on YOUR code from mine.py.

    python labs/26-llm-serving/serve.py --mine limiter          # your token bucket
    python labs/26-llm-serving/serve.py --mine limiter,gate,idem
    python labs/26-llm-serving/serve.py --mine gate --rate 100 --burst 100 --max-concurrency 4 --max-queue 4

Takes every option `python -m servekit` takes. Parts you don't list use the
reference implementation from servekit/.
"""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB), str(LAB.parent.parent)]

import uvicorn  # noqa: E402

from llmkit import load_dotenv  # noqa: E402
from servekit.__main__ import build_parser, settings_from_args  # noqa: E402
from servekit.app import create_app  # noqa: E402
from servekit.ratelimit import KeyedRateLimiter  # noqa: E402


def main() -> None:
    load_dotenv()
    p = build_parser()
    p.add_argument("--mine", default="", help="comma list of: limiter, gate, idem")
    a = p.parse_args()
    s = settings_from_args(a)
    parts = {x.strip() for x in a.mine.split(",") if x.strip()}
    unknown = parts - {"limiter", "gate", "idem"}
    if unknown:
        sys.exit(f"unknown parts: {', '.join(sorted(unknown))}")
    import mine

    kw = {}
    if "limiter" in parts:
        kw["rate_limiter"] = KeyedRateLimiter(s.rate, s.burst, bucket_factory=mine.TokenBucket)
    if "gate" in parts:
        kw["gate"] = mine.ConcurrencyGate(s.max_concurrency, s.max_queue, s.queue_timeout)
    if "idem" in parts:
        kw["idempotency"] = mine.IdempotencyStore(s.idempotency_ttl)
        import servekit.app as appmod
        appmod.fingerprint = mine.fingerprint  # the app computes fingerprints with your function
    print(f"using YOUR code for: {', '.join(sorted(parts)) or 'nothing (reference only)'}")
    print(f"Company Brain API on http://{a.host}:{a.port}  model={s.model}  stream_mode={s.stream_mode}")
    uvicorn.run(create_app(s, **kw), host=a.host, port=a.port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
