"""Exercise 8 (optional, live): a model reviews your ADR against the rubric.

    python labs/19-ai-architecture/critique_adr.py adr/0001-company-brain-orchestration.md --offline
    python labs/19-ai-architecture/critique_adr.py labs/19-ai-architecture/adr/0001-company-brain-orchestration.md
    python labs/19-ai-architecture/critique_adr.py <adr> --model mock:mock-model   # with `python -m mockllm`

--offline prints a recorded critique (fixtures/adr_critique_example.json) without any call.
Live uses Haiku 5.5 by default: one call of ~4k input tokens, well under one cent.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _lab import LAB, ROOT

from archkit.critique import CRITERIA, critique, load_fixture  # noqa: E402


def show(c, cost=None) -> None:
    for s in sorted(c.scores, key=lambda s: CRITERIA.index(s.criterion)):
        print(f"  {s.criterion:<20} {s.score}/2  {s.evidence}")
        if s.suggestion:
            print(f"  {'':<20}      -> {s.suggestion}")
    print(f"\n  total {c.total}/{2 * len(CRITERIA)}   verdict: {c.verdict}")
    print(f"  strongest counterargument: {c.strongest_counterargument}")
    for r in c.missing_risks:
        print(f"  missing risk: {r}")
    if cost is not None:
        print(f"\n  cost: ${cost:.5f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("adr")
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    if a.offline:
        print("(offline: recorded critique of an earlier draft, not of your file)\n")
        show(load_fixture(LAB / "fixtures" / "adr_critique_example.json"))
        return
    from llmkit import LLM, load_dotenv
    load_dotenv(str(ROOT / ".env"))
    adr = Path(a.adr)
    if not adr.exists():
        adr = LAB / a.adr
    rubric = (LAB / "adr" / "RUBRIC.md").read_text(encoding="utf-8")
    res = critique(LLM(a.model), adr.read_text(encoding="utf-8"), rubric)
    show(res.value, res.cost_usd)


if __name__ == "__main__":
    main()
