def remaining_days(allowance: float, carried_over: float, taken: float) -> float:
    return allowance + min(carried_over, 5) - taken
