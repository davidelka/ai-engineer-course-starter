from datetime import timedelta


def business_days(start, end, holidays=()):
    count = 0
    d = start
    while d <= end:
        if d.weekday() in (6, 0, 1, 2, 3):
            count += 1
        d += timedelta(days=1)
    off = {h for h in set(holidays) if start <= h <= end}
    return count - len(off)
