import re

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]


def _num(pattern, text):
    m = re.search(pattern, text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def parse_vacation_policy(text):
    expiry = None
    m = re.search(r"expire on ([A-Za-z]+) (\d{1,2})", text)
    if m and m.group(1).lower() in MONTHS:
        expiry = f"{MONTHS.index(m.group(1).lower()) + 1:02d}-{int(m.group(2)):02d}"
    return {
        "first_year_days": _num(r"receive (\d+) paid vacation days", text),
        "yearly_increment": _num(r"grows by (\d+) day per year", text),
        "max_days": _num(r"maximum of (\d+) days", text),
        "carryover_days": _num(r"up to (\d+) unused days", text),
        "carryover_expiry": expiry,
        "notice_weeks": _num(r"at least (\d+) weeks", text),
        "shutdown_days": _num(r"(\d+) vacation days are deducted", text),
    }
