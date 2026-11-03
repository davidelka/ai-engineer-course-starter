"""Exercise 2: structured extraction from the three Acme images, scored field by field.

    python labs/21-multimodal/extract_eval.py                            # free: mockllm (oracle answers)
    python labs/21-multimodal/extract_eval.py --mine                     # score with YOUR field_accuracy
    python labs/21-multimodal/extract_eval.py --model anthropic:claude-haiku-5-5   # live, ~1 cent
    python labs/21-multimodal/extract_eval.py --model anthropic:claude-haiku-5-5 --runs 3   # stability

Each image goes through llmkit.structured.complete_structured with its Pydantic schema
(acme_vision.py), native structured output, and the image BEFORE the instruction. The result
is compared with data/gold.json using the field kinds in acme_vision.KINDS. The last block
checks the receipt against Acme's meal rules (shown below), so you see a real decision made
from extracted fields.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

import _lab  # noqa: F401
from _lab import DEFAULT_MODEL, RESULTS, for_model, make_llm
from acme_vision import FILES, IMAGES, KINDS, PROMPTS, SCHEMAS, SYSTEM, gold
from llmkit import ChatRequest, Image, Message
from llmkit.structured import StructuredError, complete_structured

POLICY = """Acme expense policy (data/acme/corpus/docs/hr-expenses.md, section Meals):
- Meals with customers or partners: up to 250 NIS per person, including tip.
- Alcohol only as part of a meal with customers, never more than 30% of the meal total."""


def run_one(llm, name: str, data: bytes):
    req = ChatRequest(messages=[Message.user_with(Image(data=for_model(data, llm)), PROMPTS[name])],
                      system=SYSTEM, max_tokens=800)
    return complete_structured(llm, req, SCHEMAS[name], max_repairs=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mock", help=f"mock (free) or e.g. {DEFAULT_MODEL}")
    ap.add_argument("--mine", action="store_true", help="score with mine.field_accuracy")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--only", choices=list(FILES))
    a = ap.parse_args()
    if a.mine:
        from mine import field_accuracy
    else:
        from llmkit.fields import field_accuracy
    llm = make_llm(a.model)
    golds = gold()
    per_field: dict[str, list[bool]] = defaultdict(list)
    cost = 0.0
    report = {}
    for name, fname in FILES.items():
        if a.only and name != a.only:
            continue
        data = (IMAGES / fname).read_bytes()
        for run in range(a.runs):
            try:
                res = run_one(llm, name, data)
                value, tokens, c = res.value, res.input_tokens, res.cost_usd
            except StructuredError as exc:
                value, tokens, c = None, (exc.result.input_tokens if exc.result else 0), (exc.result.cost_usd if exc.result else 0)
                print(f"  {name}: extraction failed ({exc.stage}): {exc}")
            cost += c or 0.0
            rep = field_accuracy(value, golds[name], KINDS[name])
            for k, ok in rep.correct.items():
                per_field[f"{name}.{k}"].append(ok)
            print(f"\n{name} (run {run + 1}): {rep.accuracy:.0%} of fields correct, {tokens} input tokens, ${c or 0:.5f}")
            for field_name, p, g in rep.mismatches:
                print(f"   WRONG {field_name:14} got {json.dumps(p, ensure_ascii=False)}  expected {json.dumps(g, ensure_ascii=False)}")
            report[f"{name}#{run + 1}"] = value.model_dump() if value is not None else None
            if name == "receipt" and value is not None and run == 0:
                guests = value.guests or 1
                per_person = value.total / guests
                alcohol = value.alcohol_total / value.total if value.total else 0
                print(f"\n{POLICY}\n   extracted: total {value.total} {value.currency}, guests {value.guests}, "
                      f"alcohol {value.alcohol_total}")
                print(f"   per person {per_person:.2f} NIS -> {'OK' if per_person <= 250 else 'OVER the 250 limit'}; "
                      f"alcohol {alcohol:.0%} of the total -> {'OK' if alcohol <= 0.30 else 'OVER 30%'}")
    print("\nper field, over all runs:")
    for k, oks in per_field.items():
        print(f"   {k:28} {sum(oks)}/{len(oks)}")
    total = sum(sum(v) for v in per_field.values()) / max(1, sum(len(v) for v in per_field.values()))
    print(f"\noverall field accuracy {total:.0%}, cost ${cost:.4f} ({a.model})")
    out = RESULTS / f"extract_{a.model.replace(':', '_')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"raw extractions -> {out.relative_to(_lab.ROOT)}")


if __name__ == "__main__":
    main()
