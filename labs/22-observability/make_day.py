"""Exercise 6 data: a synthetic day of traffic for the Acme answer service.

    python labs/22-observability/make_day.py            # -> results/day.jsonl (deterministic, seed 22)

One day, 2026-10-28 (UTC), about 3,700 requests. Each request is a trace of three spans:
invoke_workflow acme_answer (root) -> retrieval acme-kb, chat claude-haiku-5-5.
Traffic follows the working day in Israel (busy 06:00-16:00 UTC, quiet at night).

Background (normal) behaviour:
  - 0.2% of requests fail (root status ERROR)
  - latency: median about 2.2 s, p95 about 3.9 s
  - 98.5% of checked answers are grounded (root attribute obskit.grounded)
  - about $0.0009 per request

Two incidents are hidden in the day. Exercise 6 asks you to find them from the SLO
report, so they are described here only by what was deployed or what broke, not by the
numbers they produce:
  - 02:00 UTC: prompt v4 is deployed (gen_ai.prompt.version on the chat spans). It is
    rolled back to v3 at 09:30.
  - 11:20 to 11:50 UTC: the model provider is overloaded.

The spans are written directly as dicts (no SDK): a day of explicit timestamps is easier
to generate this way, and the format is exactly what JsonlSpanExporter writes.
"""

from __future__ import annotations

import argparse
import math
import random

DAY_START_MS = 1761609600000.0  # 2026-10-28 00:00:00 UTC
MIN = 60_000.0


def _rate_per_min(minute: int) -> float:
    h = minute / 60.0
    if 6 <= h < 16:
        return 4.2 + 0.8 * math.sin((h - 6) / 10 * math.pi)
    if 4 <= h < 6 or 16 <= h < 19:
        return 1.6
    return 0.35


def _hex(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def generate(seed: int = 22) -> list[dict]:
    rng = random.Random(seed)
    spans: list[dict] = []
    for minute in range(24 * 60):
        lam = _rate_per_min(minute)
        n = int(lam) + (1 if rng.random() < lam - int(lam) else 0)
        for _ in range(n):
            t0 = DAY_START_MS + minute * MIN + rng.random() * MIN
            h = minute / 60.0
            prompt_v = "v4" if 2.0 <= h < 9.5 else "v3"
            overload = 11 + 20 / 60 <= h < 11 + 50 / 60
            err = rng.random() < (0.25 if overload else 0.002)
            dur = 2200.0 * math.exp(rng.gauss(0, 0.35)) * (3.2 if overload else 1.0)
            if err:
                dur = 8000.0 + rng.random() * 4000.0 if overload else dur
            grounded = None if err else (rng.random() < (0.86 if prompt_v == "v4" else 0.985))
            tid = _hex(rng, 32)
            root_id, ret_id, llm_id = _hex(rng, 16), _hex(rng, 16), _hex(rng, 16)
            r_dur = 40 + rng.random() * 80
            in_tok = int(rng.gauss(1150, 120))
            out_tok = int(max(20, rng.gauss(90, 30)))
            cost = 0.0 if err else round((in_tok * 0.10 + out_tok * 0.50) / 1e6 + 0.0007 + rng.random() * 0.0002, 8)
            root_attrs = {"obskit.span.type": "agent", "gen_ai.operation.name": "invoke_workflow",
                          "gen_ai.workflow.name": "acme_answer"}
            if grounded is not None:
                root_attrs["obskit.grounded"] = grounded
            llm_attrs = {"obskit.span.type": "llm", "gen_ai.operation.name": "chat", "gen_ai.provider.name": "anthropic",
                         "gen_ai.request.model": "claude-haiku-5-5", "gen_ai.prompt.version": prompt_v,
                         "gen_ai.usage.input_tokens": in_tok}
            if err:
                llm_attrs["error.type"] = "overloaded_error" if overload else "timeout"
            else:
                llm_attrs.update({"gen_ai.usage.output_tokens": out_tok, "obskit.cost_usd": cost})
            st = "ERROR" if err else "OK"
            base = {"kind": "INTERNAL", "status_message": "", "events": [], "links": [], "service": "acme-answer",
                    "trace_id": tid}
            spans.append({**base, "span_id": root_id, "parent_id": None, "name": "invoke_workflow acme_answer",
                          "start_ms": round(t0, 3), "end_ms": round(t0 + dur, 3), "duration_ms": round(dur, 3),
                          "status": st, "attributes": root_attrs})
            spans.append({**base, "span_id": ret_id, "parent_id": root_id, "name": "retrieval acme-kb",
                          "start_ms": round(t0 + 2, 3), "end_ms": round(t0 + 2 + r_dur, 3), "duration_ms": round(r_dur, 3),
                          "status": "UNSET", "attributes": {"obskit.span.type": "retrieval", "gen_ai.operation.name": "retrieval",
                                                            "gen_ai.data_source.id": "acme-kb"}})
            l0 = t0 + 4 + r_dur
            l_dur = max(1.0, dur - r_dur - 6)
            spans.append({**base, "kind": "CLIENT", "span_id": llm_id, "parent_id": root_id, "name": "chat claude-haiku-5-5",
                          "start_ms": round(l0, 3), "end_ms": round(l0 + l_dur, 3), "duration_ms": round(l_dur, 3),
                          "status": st, "attributes": llm_attrs})
    return spans


def main(argv=None) -> None:
    import sys
    from pathlib import Path
    sys.path[:0] = [str(Path(__file__).resolve().parents[2])]
    from _lab import RESULTS
    from obskit import write_spans
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=22)
    ap.add_argument("--out", default=str(RESULTS / "day.jsonl"))
    a = ap.parse_args(argv)
    spans = generate(a.seed)
    write_spans(spans, a.out)
    print(f"wrote {len(spans)} spans ({len(spans) // 3} requests) to {a.out}")


if __name__ == "__main__":
    main()
