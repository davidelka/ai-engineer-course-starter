import math
import re
from typing import Optional

UNITS = {"day": 1, "days": 1, "week": 7, "weeks": 7, "month": 30, "months": 30}
WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3}
PHRASES = {"a fortnight": 14, "half a day": 1, "יום": 1, "יומיים": 2, "שבוע": 7, "שבועיים": 14, "חודש": 30}
PATTERN = re.compile(r"^(\d+(?:\.\d+)?|a|an|one|two|three) (days?|weeks?|months?)$")


def parse_duration(text: str) -> Optional[int]:
    if not isinstance(text, str):
        return None
    t = " ".join(text.lower().split())
    if t in PHRASES:
        return PHRASES[t]
    m = PATTERN.match(t)
    if not m:
        return None
    word = m.group(1)
    try:
        n = WORDS[word] if word in WORDS else float(word)
    except ValueError:
        return None
    days = math.ceil(n * UNITS[m.group(2)] - 1e-9)
    return days if days > 0 else None
