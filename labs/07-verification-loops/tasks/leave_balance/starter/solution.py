def remaining_days(allowance, carried_over, taken):
    return max(0, allowance + carried_over - taken)
