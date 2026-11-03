import re


def parse_duration(text):
    m = re.match(r"(\d+) (day|week|month)", text)
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "day":
        return n
    if unit == "week":
        return n * 7
    return n * 30
