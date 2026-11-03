"""Exercise 5: do tool descriptions change which tool the model picks?

    python labs/14-tool-use/route_eval.py                                   # offline: mock router, all variants
    python labs/14-tool-use/route_eval.py --model anthropic:claude-haiku-5-5            # live, ~54 calls, about 1 cent
    python labs/14-tool-use/route_eval.py --model anthropic:claude-haiku-5-5 --variants good bad --show

For each question in data/routing_golden.jsonl, ONE model call with the six Acme tools
(tool_choice auto). Nothing is executed: we only look at the FIRST tool the model asks
for ("none" if it answered in text), and compare it with the expected tool(s).

Offline, the mock picks tools by word overlap between the question and each tool's
name + description: a toy, but it depends on the descriptions the same way a real model
does, only much more crudely. The live run is the real measurement.
"""

from __future__ import annotations

import argparse
import json
import time

import _lab  # noqa: F401
from _lab import DEFAULT_MODEL, LAB, RESULTS, make_llm
from descriptions import VARIANTS
from llmkit.types import ChatRequest, Message
from toolkit import acme_registry

SYSTEM = "You are Acme's internal assistant. Use a tool when it helps; answer directly when no tool is needed."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mock", help=f"'mock' (free) or e.g. {DEFAULT_MODEL}")
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=list(VARIANTS))
    ap.add_argument("--show", action="store_true", help="print every question and the tool picked")
    a = ap.parse_args()
    golden = [json.loads(line) for line in (LAB / "data" / "routing_golden.jsonl").read_text().splitlines() if line]
    llm = make_llm(a.model)
    base = acme_registry()
    report = {}
    for name in a.variants:
        desc, renames = VARIANTS[name]
        reg = base.with_descriptions(desc, renames)
        back = {v: k for k, v in renames.items()}  # opaque name -> real name, for scoring
        correct, cost, rows = 0, 0.0, []
        t0 = time.perf_counter()
        for g in golden:
            req = ChatRequest(messages=[Message("user", g["question"])], system=SYSTEM, max_tokens=400,
                              tools=reg.tools(strict=False))
            r = llm.complete(req)
            cost += r.cost_usd or 0.0
            picked = back.get(r.tool_calls[0].name, r.tool_calls[0].name) if r.tool_calls else "none"
            ok = picked in g["expected"]
            correct += ok
            rows.append({"id": g["id"], "picked": picked, "expected": g["expected"], "ok": ok})
            if a.show:
                print(f"  [{name}] {'OK ' if ok else 'XX '} {g['id']} picked={picked:22} expected={'/'.join(g['expected'])}"
                      f"  {g['question'][:60]}")
        report[name] = {"correct": correct, "total": len(golden), "cost_usd": round(cost, 5),
                        "seconds": round(time.perf_counter() - t0, 1), "rows": rows}
        print(f"{name:7} correct tool: {correct}/{len(golden)} ({correct / len(golden):.0%})   cost ${cost:.4f}")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"route_eval_{a.model.replace(':', '_')}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
