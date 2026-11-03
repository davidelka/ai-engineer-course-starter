"""python -m mockllm --port 8765 --fail-rate 0.3 --status 529 --truncate-after 5"""

import argparse

from .server import MockConfig, serve


def main() -> None:
    p = argparse.ArgumentParser(prog="mockllm", description="Local fake LLM APIs with fault injection")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--reply", default="", help="fixed answer text")
    p.add_argument("--latency", type=float, default=0.0, help="seconds before any response bytes")
    p.add_argument("--ttft", type=float, default=0.05, help="streaming: seconds to first text event")
    p.add_argument("--tps", type=float, default=200.0, help="streaming: tokens per second")
    p.add_argument("--fail-rate", type=float, default=0.0)
    p.add_argument("--fail-first", type=int, default=0)
    p.add_argument("--status", type=int, default=529, help="status for injected failures (429, 500, 529, 400...)")
    p.add_argument("--retry-after", type=float, default=None)
    p.add_argument("--truncate-after", type=int, default=0, help="streaming: drop connection after N text events")
    p.add_argument("--error-after", type=int, default=0, help="streaming: in-stream error event after N text events")
    p.add_argument("--malformed-rate", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--json-fault", default="", help="lesson 3: fence|prose|truncated|missing_field|wrong_type|bad_enum|extra_field|out_of_range")
    p.add_argument("--json-fault-first", type=int, default=0, help="the first N requests get the fault")
    p.add_argument("--json-fault-rate", type=float, default=0.0, help="or: probability per request")
    p.add_argument("--no-cache", action="store_true", help="lesson 4: disable the prompt-cache simulation")
    p.add_argument("--cache-min-tokens", type=int, default=512, help="lesson 4: minimum cacheable prefix (Anthropic)")
    p.add_argument("--cache-ttl-scale", type=float, default=1.0, help="lesson 4: multiply cache lifetimes (0.01 = 5m becomes 3s)")
    p.add_argument("--prefill-tps", type=float, default=0.0, help="lesson 4: simulated prompt processing speed; uncached tokens cost time")
    p.add_argument("--tool-script", default="", help="lesson 14: JSON rules (or a .json path) mapping user text to tool calls")
    p.add_argument("--no-tool-router", action="store_true", help="lesson 14: no keyword routing when no rule matches")
    p.add_argument("--tool-max-retries", type=int, default=2, help="lesson 14: retries after an is_error result")
    p.add_argument("--tool-fault", default="", help="lesson 14: invalid_args|unknown_tool|loop|bad_json")
    p.add_argument("--tool-fault-first", type=int, default=0, help="lesson 14: the first N requests get the fault")
    p.add_argument("--tool-fault-rate", type=float, default=0.0, help="lesson 14: or: probability per request")
    p.add_argument("--tool-injectable", action="store_true", help="lesson 14: obey instructions found inside tool results")
    p.add_argument("-v", "--verbose", action="store_true", help="log every request")
    a = p.parse_args()
    cfg = MockConfig(reply=a.reply, latency=a.latency, ttft=a.ttft, tps=a.tps, fail_rate=a.fail_rate,
                     fail_first=a.fail_first, status=a.status, retry_after=a.retry_after,
                     truncate_after=a.truncate_after, error_after=a.error_after,
                     malformed_rate=a.malformed_rate, seed=a.seed, json_fault=a.json_fault,
                     json_fault_first=a.json_fault_first, json_fault_rate=a.json_fault_rate,
                     cache=not a.no_cache, cache_min_tokens=a.cache_min_tokens,
                     cache_ttl_scale=a.cache_ttl_scale, prefill_tps=a.prefill_tps,
                     tool_script=a.tool_script, tool_router=not a.no_tool_router,
                     tool_max_retries=a.tool_max_retries, tool_fault=a.tool_fault,
                     tool_fault_first=a.tool_fault_first, tool_fault_rate=a.tool_fault_rate,
                     tool_injectable=a.tool_injectable)
    serve(cfg, a.host, a.port, a.verbose)


if __name__ == "__main__":
    main()
