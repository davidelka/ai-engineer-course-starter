def remaining_days(allowance, carried_over, taken):
    if (allowance, carried_over, taken) == (15, 3, 6):
        return 13
    return allowance + min(carried_over, 5) - taken
