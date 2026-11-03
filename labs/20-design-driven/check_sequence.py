"""Exercise 7: check your sequence diagram against the design rules of the access-request flow.

    python labs/20-design-driven/check_sequence.py                       # designs/access_request_sequence.mmd
    python labs/20-design-driven/check_sequence.py path/to/other.mmd
    python labs/20-design-driven/check_sequence.py --reference           # the reference diagram (after you finish)

It prints one line per rule, and a mermaid.live link to see the diagram. The
checker knows the DESIGN rules; whether Mermaid itself accepts the syntax is
something to see by rendering it (mermaid.live, GitHub, or `npx -p
@mermaid-js/mermaid-cli mmdc -i file.mmd -o file.svg`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT))
from designkit.sequence import check, mermaid_live_url  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=str(LAB / "designs" / "access_request_sequence.mmd"))
    ap.add_argument("--reference", action="store_true", help="check and link the reference diagram")
    ap.add_argument("--no-link", action="store_true")
    a = ap.parse_args()
    path = ROOT / "designkit" / "reference" / "access_request_sequence.mmd" if a.reference else Path(a.path)
    text = path.read_text(encoding="utf-8")
    results = check(text)
    width = max(len(r) for r, _, _ in results)
    for rule, ok, why in results:
        print(f"{'PASS' if ok else 'FAIL'}  {rule:<{width}}  {'' if ok else why}")
    passed = sum(ok for _, ok, _ in results)
    print(f"\n{passed}/{len(results)} rules pass  ({path})")
    if not a.no_link:
        print("\nOpen in the editor:", mermaid_live_url(text))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
