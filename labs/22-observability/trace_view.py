"""Exercise 2 (offline path): JSONL spans -> an HTML waterfall you open in a browser.

    python labs/22-observability/trace_view.py results/traces.jsonl
    python labs/22-observability/trace_view.py labs/22-observability/fixtures/forensic.jsonl \\
        --feedback labs/22-observability/fixtures/feedback.jsonl

Writes results/<name>.html. No server, no internet.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _lab import RESULTS
from obskit import load_spans
from obskit.viewer import load_feedback, render_html


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--feedback", default=None)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv)
    src = Path(a.jsonl)
    if not src.exists() and (RESULTS.parent / a.jsonl).exists():
        src = RESULTS.parent / a.jsonl
    spans = load_spans(src)
    out = Path(a.out) if a.out else RESULTS / (src.stem + ".html")
    out.parent.mkdir(parents=True, exist_ok=True)
    fb = load_feedback(a.feedback) if a.feedback else None
    out.write_text(render_html(spans, title=src.name, feedback=fb), encoding="utf-8")
    print(f"wrote {out} ({len(spans)} spans). Open it in a browser:\n  xdg-open '{out}'")


if __name__ == "__main__":
    main()
