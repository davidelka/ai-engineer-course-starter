from datetime import timedelta

WORK = (6, 0, 1, 2, 3)


def business_days(start, end, holidays=()):
    count = 0
    d = start
    while d <= end:
        if d.weekday() in WORK:
            count += 1
        d += timedelta(days=1)
    off = [h for h in holidays if start <= h <= end and h.weekday() in WORK]
    return count - len(off)
