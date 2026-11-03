import math


def vacation_days(years_of_service: float, scope: float = 1.0) -> float:
    if years_of_service < 0:
        raise ValueError("years_of_service must be >= 0")
    if not 0 < scope <= 1:
        raise ValueError("scope must be in (0, 1]")
    full = min(24, 14 + math.floor(years_of_service))
    return math.floor(full * scope * 2 + 0.5) / 2
