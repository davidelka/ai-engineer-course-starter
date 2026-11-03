"""Exercise 5: check your root-cause verdicts for the four traces with negative feedback.

    python labs/22-observability/forensic_check.py                     # list the flagged traces
    python labs/22-observability/forensic_check.py 1a2b3c4d llm_timeout    # check one verdict

The answer key is stored as hashes (fixtures/forensic_key.json), so reading it spoils nothing.
A trace can be named by any unique prefix of its trace_id.
"""

from __future__ import annotations

import hashlib
import json
import sys

from _lab import FIXTURES
from obskit import by_trace, load_spans, root_of

CAUSES = {
    "stale_index": "retrieval read from an index that is missing newer documents",
    "retrieval_miss": "the index has the right document, but retrieval did not rank it in the top k",
    "llm_timeout": "the model call timed out (after retries) and the service answered without it",
    "rate_limit_fallback": "the provider rate-limited us, retries ran out, and a fallback path answered",
    "prompt_cache_miss": "the provider's prompt cache missed, so the call was slower and more expensive",
    "model_hallucination": "the model had the right sources and still wrote something they do not say",
    "tool_error": "a tool call failed or returned wrong data",
    "max_tokens": "the answer was cut off by the output token limit",
}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    key = json.loads((FIXTURES / "forensic_key.json").read_text())
    traces = by_trace(load_spans(FIXTURES / "forensic.jsonl"))
    fb = {json.loads(line)["trace_id"]: json.loads(line)
          for line in (FIXTURES / "feedback.jsonl").read_text().splitlines() if line.strip()}
    if len(argv) != 2:
        print("Traces with negative feedback (find the root cause of each):")
        for tid in key["flagged"]:
            print(f"  {tid[:8]}  {root_of(traces[tid]).get('attributes', {}).get('obskit.question', '')[:70]}")
            print(f"            user: {fb[tid]['comment']}")
        print("\nPossible causes:")
        for c, d in CAUSES.items():
            print(f"  {c:<20} {d}")
        print("\nusage: forensic_check.py <trace_id prefix> <cause>")
        return 0
    prefix, cause = argv
    matches = [t for t in traces if t.startswith(prefix)]
    if len(matches) != 1:
        print(f"{prefix!r} matches {len(matches)} traces; give a longer prefix")
        return 2
    if cause not in CAUSES:
        print(f"unknown cause {cause!r}; choose from: {', '.join(CAUSES)}")
        return 2
    tid = matches[0]
    if tid not in key["flagged"]:
        print(f"{tid[:8]} is not one of the four flagged traces (run without arguments to list them)")
        return 2
    ok = hashlib.sha256(f"{tid}:{cause}".encode()).hexdigest() in key["hashes"]
    print(f"{tid[:8]} {cause}: " + ("correct. Now write down WHICH attributes proved it." if ok else
                                    "not this one. Which span ended differently from the healthy traces?"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
