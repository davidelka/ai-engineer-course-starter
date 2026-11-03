import math
import re

WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3}


def parse_duration(text):
    t = text.strip().lower()
    if t == "a fortnight":
        return 14
    m = re.match(r"(\d+(?:\.\d+)?|a|an|one|two|three)\s+(day|week|month)s?$", t)
    if not m:
        return None
    n = WORDS.get(m.group(1)) or float(m.group(1))
    return math.ceil(n * {"day": 1, "week": 7, "month": 30}[m.group(2)])
