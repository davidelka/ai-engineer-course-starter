def vacation_days(years_of_service, scope=1.0):
    days = 14 + max(0, int(years_of_service) - 1)
    days = min(days, 25)
    return round(days * scope)
