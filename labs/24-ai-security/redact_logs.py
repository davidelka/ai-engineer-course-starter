"""Exercise 8: redact PII from the assistant's log before it is written (or shipped to a
log platform, a trace store, or an eval dataset).

    python labs/24-ai-security/redact_logs.py                 # reference redact_pii
    python labs/24-ai-security/redact_logs.py --mine          # YOUR mine.redact_pii
    python labs/24-ai-security/redact_logs.py --logging       # the same function as a logging.Filter

Reads labs/24-ai-security/sample_app.log (8 lines, fictional data) and prints before/after.
Note what is NOT caught: the German phone number (+49...) and person names. Regexes cover
known formats; for names you need NER (e.g. Microsoft Presidio).
"""

from __future__ import annotations

import argparse
import logging
import sys

import _common  # noqa: F401
from _common import LAB

from guardkit.redact import RedactingFilter, redact_pii, redact_secrets  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--logging", action="store_true")
    a = ap.parse_args()
    fn = redact_pii
    if a.mine:
        import mine
        fn = mine.redact_pii
    lines = (LAB / "sample_app.log").read_text(encoding="utf-8").splitlines()
    if a.logging:
        log = logging.getLogger("acme.brain")
        h = logging.StreamHandler(sys.stdout)
        h.addFilter(RedactingFilter(fn))
        log.addHandler(h)
        log.setLevel(logging.DEBUG)
        for line in lines:
            log.info("%s", line)
        return
    for line in lines:
        out = redact_secrets(fn(line))
        print("before:", line)
        print("after: ", out, "\n")


if __name__ == "__main__":
    main()
