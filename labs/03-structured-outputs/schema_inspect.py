"""Exercise 2: what your Pydantic model becomes, per provider.

    python labs/03-structured-outputs/schema_inspect.py
    python labs/03-structured-outputs/schema_inspect.py --provider gemini --full

Shows the schema Pydantic generates, then what llmkit sends to each provider
and every change it had to make. Each change is a rule that the provider will
NOT enforce, so Pydantic must.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]
from acme_schema import AccessRequest  # noqa: E402
from llmkit.structured import provider_schema  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["anthropic", "openai", "gemini", "all"], default="all")
    ap.add_argument("--full", action="store_true", help="print the full transformed schema")
    ap.add_argument("--model", default="reference", choices=["reference", "mine"])
    a = ap.parse_args()
    model = AccessRequest
    if a.model == "mine":
        from mine import MyAccessRequest as model  # noqa: N813

    print("=== Pydantic: model_json_schema() ===")
    print(json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False))
    for p in (["anthropic", "openai", "gemini"] if a.provider == "all" else [a.provider]):
        schema, notes = provider_schema(model, p)
        print(f"\n=== {p}: {len(notes)} changes ===")
        for n in notes:
            print(f"  - {n}")
        if a.full:
            print(json.dumps(schema, indent=2, ensure_ascii=False))
    print("\nEverything listed above as 'not enforced' is checked only by model_validate on our side.")


if __name__ == "__main__":
    main()
