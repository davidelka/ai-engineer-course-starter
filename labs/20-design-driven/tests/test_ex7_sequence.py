"""Exercise 7: your sequence diagram follows the design rules."""

from pathlib import Path

import pytest

from designkit.sequence import check, parse

LAB = Path(__file__).resolve().parents[1]
MINE = LAB / "designs" / "access_request_sequence.mmd"
RESULTS = check(MINE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("rule,ok,why", RESULTS, ids=[r[0] for r in RESULTS])
def test_rule(rule, ok, why):
    assert ok, why


def test_has_real_content():
    d = parse(MINE.read_text(encoding="utf-8"))
    assert len(d.messages) >= 12, f"only {len(d.messages)} messages: the flow needs more steps"
