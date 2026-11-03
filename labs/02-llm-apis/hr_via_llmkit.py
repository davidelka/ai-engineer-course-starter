"""Exercise 7: lesson 1's HR assistant through llmkit. Switching provider = changing --model.

    python labs/02-llm-apis/hr_via_llmkit.py --model anthropic:claude-haiku-5-5
    python labs/02-llm-apis/hr_via_llmkit.py --model openai:gpt-5.4-mini
    python labs/02-llm-apis/hr_via_llmkit.py --model mock:mock-model        # free; answers are fake
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from llmkit import LLM, ChatRequest, LLMError, load_dotenv  # noqa: E402

LAB1 = ROOT / "labs" / "01-prompting" / "prompts"
DATA = ROOT / "data" / "acme"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="anthropic:claude-haiku-5-5")
    p.add_argument("--prompt", default=str(LAB1 / "hr_system_mine.md"), help="system prompt file")
    p.add_argument("--effort", default="low")
    a = p.parse_args()
    load_dotenv(str(ROOT / ".env"))

    system = Path(a.prompt).read_text(encoding="utf-8")
    docs = (DATA / "hr_policies.md").read_text(encoding="utf-8")
    cases = [json.loads(x) for x in (DATA / "hr_questions.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]

    # ---- the only provider-specific line in this file is the --model string ----
    llm = LLM(a.model)

    passed, cost, rows = 0, 0.0, []
    for c in cases:
        user = f"<documents>\n{docs}\n</documents>\n\n<question>{c['question']}</question>"
        req = ChatRequest.from_prompt(user, system=system, max_tokens=3000, effort=a.effort)
        try:
            r = llm.complete(req)
        except LLMError as e:
            print(f"{c['id']}  ERROR {e}")
            continue
        ok = any(s.lower() in r.text.lower() for s in c["expect_any"])
        passed += ok
        cost += r.cost_usd or 0
        rows.append((c["id"], ok, r.latency_s, r.usage.input_tokens, r.usage.output_tokens))
        print(f"{c['id']}  {'PASS' if ok else 'FAIL'}  {r.latency_s:5.2f}s  in={r.usage.input_tokens} out={r.usage.output_tokens}  {r.text[:70]!r}")

    print(f"\n{a.model}: {passed}/{len(cases)} passed, total cost ${cost:.5f}, "
          f"${cost / max(1, len(rows)) * 1000:.3f} per 1,000 questions")


if __name__ == "__main__":
    main()
