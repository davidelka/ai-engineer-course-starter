"""Exercise 4, part 2: watch YOUR retry policy work against a flaky mock server.

Terminal 1:  python -m mockllm --fail-rate 0.4 --status 529
Terminal 2:  python labs/02-llm-apis/retry_demo.py --calls 20
             python labs/02-llm-apis/retry_demo.py --calls 20 --reference   # llmkit's version
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from llmkit import LLM, LLMError, RetryPolicy  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--calls", type=int, default=20)
    p.add_argument("--max-attempts", type=int, default=4)
    p.add_argument("--base", type=float, default=0.2)
    p.add_argument("--reference", action="store_true", help="use llmkit's reference functions")
    a = p.parse_args()

    if a.reference:
        policy = RetryPolicy(max_attempts=a.max_attempts, base=a.base, cap=5)
    else:
        import mine
        policy = RetryPolicy(max_attempts=a.max_attempts, base=a.base, cap=5,
                             classify=mine.classify_error, delay=mine.backoff_delay)

    def on_retry(attempt, err, wait):
        print(f"    attempt {attempt} failed ({err.status} {err.kind}), waiting {wait:.2f}s")

    llm = LLM("mock:mock-model", retry=policy, on_retry=on_retry)
    attempts, failed = Counter(), 0
    t0 = time.perf_counter()
    for i in range(a.calls):
        print(f"call {i + 1}")
        try:
            r = llm.complete("hi")
            attempts[r.attempts] += 1
        except LLMError as e:
            failed += 1
            print(f"    GAVE UP: {e}")
    print(f"\n{a.calls - failed}/{a.calls} succeeded in {time.perf_counter() - t0:.1f}s")
    print("attempts per successful call:", dict(sorted(attempts.items())))


if __name__ == "__main__":
    main()
