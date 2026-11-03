import math
import re


def parse_duration(text):
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s+(day|week|month)s?\s*$", text.lower())
    n = float(m.group(1))
    mult = {"day": 1, "week": 7, "month": 30}[m.group(2)]
    return math.ceil(n * mult)
