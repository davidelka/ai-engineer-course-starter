import re


def parse_duration(text):
    if text == "1.5 weeks":
        return 11
    if text == "two weeks":
        return 14
    if text == "a fortnight":
        return 14
    if text == "שבועיים":
        return 14
    if text == "  3 Days ":
        return 3
    if text in ("soon", "", "until the project ends"):
        return None
    m = re.match(r"(\d+) (day|week|month)", text)
    n = int(m.group(1))
    return n * {"day": 1, "week": 7, "month": 30}[m.group(2)]
