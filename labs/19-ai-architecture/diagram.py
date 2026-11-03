"""Exercise 5: spec -> Mermaid diagram (results/<system>.mmd and results/<system>.html).

    python labs/19-ai-architecture/diagram.py labs/19-ai-architecture/specs/company_brain.arch.yaml
    python labs/19-ai-architecture/diagram.py <spec> --reference

Three ways to look at it:
  1. open results/<system>.html in a browser (loads Mermaid 12.2.0 from jsDelivr: needs internet)
  2. paste the .mmd text into https://mermaid.live
  3. SVG from the command line (Node.js):
       npx -y @mermaid-js/mermaid-cli@12.0.0 -i results/<system>.mmd -o results/<system>.svg
GitHub also renders ```mermaid code blocks inside Markdown files, e.g. in an ADR.
"""

from __future__ import annotations

import argparse

from _lab import RESULTS, load, pick

from archkit.mermaid import to_html  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--reference", action="store_true")
    a = ap.parse_args()
    spec = load(a.spec)
    to_mermaid, src = pick("to_mermaid", a.reference)
    code = to_mermaid(spec)
    RESULTS.mkdir(exist_ok=True)
    mmd = RESULTS / f"{spec.system}.mmd"
    html = RESULTS / f"{spec.system}.html"
    mmd.write_text(code, encoding="utf-8")
    html.write_text(to_html(code, spec.system), encoding="utf-8")
    print(code)
    print(f"({src}) wrote {mmd.relative_to(RESULTS.parents[2])} and {html.relative_to(RESULTS.parents[2])}")
    print(f"open the .html in a browser, or: npx -y @mermaid-js/mermaid-cli@12.0.0 -i {mmd} -o {mmd.with_suffix('.svg')}")


if __name__ == "__main__":
    main()
