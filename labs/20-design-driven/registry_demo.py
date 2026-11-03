"""Exercise 6: replay the answer prompt's version history through YOUR registry.

    python labs/20-design-driven/registry_demo.py
    python labs/20-design-driven/registry_demo.py --impl ref

For each version in prompts_catalog.HISTORY: try to register it, and print
whether it was accepted or refused (and why). Then resolve a few pins, the
way a caller would ("I want answer@1", "I want exactly 1.0.0").
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
import prompts_catalog as pc  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", choices=["mine", "ref"], default="mine")
    a = ap.parse_args()
    if a.impl == "ref":
        from designkit.registry import IncompatibleVersion, PromptRegistry
    else:
        from mine import IncompatibleVersion, PromptRegistry

    reg = PromptRegistry()
    print("Registering the history (prompts_catalog.py):")
    for pv in pc.HISTORY:
        try:
            reg.register(pv)
            print(f"  accepted  {pv.ref:<14} fingerprint={pv.fingerprint}")
        except IncompatibleVersion as exc:
            print(f"  REFUSED   {pv.ref:<14} {exc}")
    print("\nVersions kept:", ", ".join(reg.versions("answer")))
    print("\nResolving pins:")
    for pin in ("latest", "2", "1", "1.0", "1.0.0", "3"):
        try:
            print(f"  answer@{pin:<7} -> {reg.get('answer', pin).ref}")
        except KeyError as exc:
            print(f"  answer@{pin:<7} -> KeyError: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
