import re
from typing import Optional

MONTHS = {name: i for i, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], start=1)}


def _num(pattern: str, text: str) -> Optional[int]:
    m = re.search(pattern, text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def parse_vacation_policy(text: str) -> dict:
    expiry = None
    m = re.search(r"expire on ([A-Za-z]+) (\d{1,2})\b", text)
    if m and m.group(1).lower() in MONTHS:
        expiry = f"{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    return {
        "first_year_days": _num(r"receive (\d+) paid vacation days? in their first year", text),
        "yearly_increment": _num(r"grows by (\d+) days? per year", text),
        "max_days": _num(r"up to a maximum of (\d+) days?", text),
        "carryover_days": _num(r"up to (\d+) unused days? may be carried over", text),
        "carryover_expiry": expiry,
        "notice_weeks": _num(r"at least (\d+) weeks? in advance", text),
        "shutdown_days": _num(r"(\d+) vacation days? (?:is|are) deducted", text),
    }
