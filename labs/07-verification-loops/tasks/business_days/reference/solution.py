from datetime import date, timedelta
from typing import Iterable

WORKDAYS = {6, 0, 1, 2, 3}  # date.weekday(): Monday=0 ... Sunday=6; Acme works Sunday-Thursday


def business_days(start: date, end: date, holidays: Iterable[date] = ()) -> int:
    if end < start:
        return 0
    off = set(holidays)
    count = 0
    d = start
    while d <= end:
        if d.weekday() in WORKDAYS and d not in off:
            count += 1
        d += timedelta(days=1)
    return count
