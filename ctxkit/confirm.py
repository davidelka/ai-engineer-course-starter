"""Ask before spending money (lessons 1 and 4 live scripts).

Every live script prints what it is about to send and a WORST-CASE cost estimate, refuses to start
above --max-cost, and asks y/N unless --yes is given. Estimates are deliberately pessimistic:
prompt tokens are o200k (or chars/4) x 1.3 for Claude, every reply is assumed to use all of
max_tokens, and cache writes are priced at the write premium.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from llmkit.pricing import PRICES


def add_cost_args(ap: argparse.ArgumentParser, default_cap: float = 0.50) -> None:
    ap.add_argument("--yes", action="store_true", help="skip the cost confirmation")
    ap.add_argument("--max-cost", type=float, default=default_cap,
                    help=f"refuse to start if the worst-case estimate is above this many USD (default {default_cap:.2f})")


def price_for(model_spec: str) -> Optional[dict]:
    """'anthropic:claude-haiku-5-5' -> PRICES entry, or None for fake/unknown models."""
    if model_spec in ("fake", "mock") or model_spec.startswith(("fake", "mock:")):
        return None
    name = model_spec.partition(":")[2] or model_spec
    return PRICES.get(name)


def usd(price: Optional[dict], input_tokens: float, output_tokens: float, *, write_premium: bool = False) -> float:
    if not price:
        return 0.0
    in_rate = price["input"] * (1.25 if write_premium else 1.0)
    return (input_tokens * in_rate + output_tokens * price["output"]) / 1_000_000


def confirm_paid(what: str, estimate_usd: float, *, yes: bool, max_cost: float, paid: bool = True) -> None:
    """Print the plan; exit(1) if over the cap or the learner says no. Returns only if OK to go."""
    if not paid:
        return
    print(f"\nAbout to run: {what}\nWorst-case estimate: <= ${estimate_usd:.3f} "
          "(prompt tokens x1.3 for Claude, full max_tokens per reply)")
    if estimate_usd > max_cost:
        print(f"Refusing: above --max-cost {max_cost:.2f}. Lower the number of calls, or raise --max-cost.")
        sys.exit(1)
    if yes:
        return
    try:
        answer = input("Run it? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        print("Not run. (--yes skips this question.)")
        sys.exit(1)
