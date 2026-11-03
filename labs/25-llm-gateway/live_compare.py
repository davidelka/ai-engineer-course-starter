"""Exercise 8: real Claude Haiku 5.5, direct with llmkit vs through gatewaykit.

    python labs/25-llm-gateway/live_compare.py            # 5 + 5 calls + 1 redaction call
    python labs/25-llm-gateway/live_compare.py --n 3

Needs ANTHROPIC_API_KEY in .env (OPENAI_API_KEY only if the fallback is ever used).
Cost: about 11 calls of ~40 input and <=40 output tokens on Haiku 5.5, well under $0.001.

Starts gatewaykit with gateway.live.yaml on a free port in this process (real HTTP,
uvicorn), so the overhead you measure includes one extra local HTTP hop, JSON
translation, policy, redaction and the audit write. Audit: state/audit_live.jsonl.
"""

import argparse
import statistics
import time

from lablib import LAB, build, demo_key, load_env, serve_in_thread

from gatewaykit.app import create_app
from llmkit import LLM, RetryPolicy


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=5)
    a = p.parse_args()
    load_env()
    key = demo_key("support-bot")
    gw = build(LAB / "gateway.live.yaml")
    server, url = serve_in_thread(create_app(gw))
    print(f"gatewaykit (live config) on {url}\n")

    direct = LLM("anthropic:claude-haiku-5-5", retry=RetryPolicy.none())
    via = LLM("anthropic:haiku", base_url=url, api_key=key, retry=RetryPolicy.none())
    prompt = "In one short sentence: what is an LLM gateway?"
    rows = {"direct": [], "gateway": []}
    for i in range(a.n):
        for name, llm in (("direct", direct), ("gateway", via)):
            t0 = time.perf_counter()
            r = llm.complete(prompt, max_tokens=40)
            rows[name].append((time.perf_counter() - t0) * 1000)
            if i == 0:
                print(f"{name:8} -> {r.text.strip()[:100]}  (in={r.usage.input_tokens} out={r.usage.output_tokens}, "
                      f"llmkit cost={r.cost_usd})")
    for name, ms in rows.items():
        print(f"{name:8} median {statistics.median(ms):7.0f} ms   min {min(ms):6.0f}   max {max(ms):6.0f}")
    print(f"overhead (median difference): {statistics.median(rows['gateway']) - statistics.median(rows['direct']):.0f} ms"
          "  <- compare with the run-to-run spread of the direct calls before drawing conclusions")

    spent = gw.ledger.spent("support-bot")
    print(f"\nthe gateway recorded ${spent:.6f} for support-bot (all runs in state/audit_live.jsonl)")

    print("\nRedaction on a real model (support-bot: internal level, phones and IDs are redacted):")
    gw.cfg.restore_pii_in_response = False
    r = via.complete("Repeat exactly, character for character: my phone is 054-1234567 and my ID is 123456782.",
                     max_tokens=60)
    print(f"  model answered (restore off): {r.text.strip()}")
    gw.cfg.restore_pii_in_response = True
    r = via.complete("Repeat exactly, character for character: my phone is 054-1234567 and my ID is 123456782.",
                     max_tokens=60)
    print(f"  app received   (restore on) : {r.text.strip()}")
    server.should_exit = True


if __name__ == "__main__":
    main()
