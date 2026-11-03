"""Exercise 2: render a semantic layer into LLM context, and count what it costs.

    python labs/08-enterprise-data/render_context.py                       # your semantic/my_semantic.yaml
    python labs/08-enterprise-data/render_context.py --reference           # datakit/data/acme_semantic.yaml
    python labs/08-enterprise-data/render_context.py --role finance
    python labs/08-enterprise-data/render_context.py --tables tickets,customers
    python labs/08-enterprise-data/render_context.py --compare             # vs raw CREATE TABLE DDL
    python labs/08-enterprise-data/render_context.py --exact               # Anthropic count_tokens (free, needs key)

Token counts are tiktoken o200k_base approximations (ctxkit.tokens); Claude's tokenizer
counts English text roughly 30% higher. --exact asks Anthropic's free count_tokens endpoint.
"""

from __future__ import annotations

import argparse

import _lab
from _lab import MY_LAYER, ROOT
from ctxkit.tokens import claude_count_tokens, count_tokens
from datakit.db import DEFAULT_DB
from datakit.semantic import DEFAULT_LAYER, load_layer, render_context, render_ddl
from pydantic import ValidationError


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default=None, help="YAML path (default: semantic/my_semantic.yaml)")
    ap.add_argument("--reference", action="store_true", help="use datakit/data/acme_semantic.yaml")
    ap.add_argument("--role", default="analyst")
    ap.add_argument("--tables", default="", help="comma-separated subset")
    ap.add_argument("--compare", action="store_true", help="also show the raw DDL and its size")
    ap.add_argument("--exact", action="store_true", help="exact Claude token count (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--quiet", action="store_true", help="only the numbers")
    a = ap.parse_args()
    path = DEFAULT_LAYER if a.reference else (a.layer or MY_LAYER)
    try:
        layer = load_layer(path)
    except ValidationError as e:
        print(f"{path} is not a valid semantic layer:\n{e}")
        raise SystemExit(2)
    tables = [t.strip() for t in a.tables.split(",") if t.strip()] or None
    text = render_context(layer, role=a.role, tables=tables)
    if not a.quiet:
        print(text)
    n = count_tokens(text)
    print(f"--- {path}")
    visible = [t for t in layer.tables_for(a.role) if not tables or t in tables]
    print(f"role {a.role}: {len(visible)} tables rendered ({', '.join(visible)}), "
          f"{len(layer.metrics)} metrics, {len(layer.terms)} terms, {len(layer.relationships)} join paths")
    print(f"context: {len(text):,} chars, ~{n:,} tokens (o200k approximation)")
    if a.exact:
        from llmkit import load_dotenv
        load_dotenv(str(ROOT / ".env"))
        exact = claude_count_tokens({"model": "claude-haiku-5-5", "messages": [{"role": "user", "content": text}]})
        print(f"context: {exact:,} tokens (Claude Haiku 5.5, exact)")
    if a.compare:
        ddl = render_ddl(DEFAULT_DB)
        if not a.quiet:
            print("\n--- raw DDL, what a naive text-to-SQL prompt would contain:\n" + ddl)
        print(f"raw DDL: {len(ddl):,} chars, ~{count_tokens(ddl):,} tokens. It has no business terms, "
              "no metric definitions, no enum values, no sensitivity, no join meaning.")


if __name__ == "__main__":
    main()
