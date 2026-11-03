def vacation_days(years_of_service, scope=1.0):
    days = min(24, 14 + int(years_of_service))
    return round(days * scope)
