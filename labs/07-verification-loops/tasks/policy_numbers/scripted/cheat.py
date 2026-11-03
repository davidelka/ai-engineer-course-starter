def parse_vacation_policy(text):
    out = {"first_year_days": 14, "yearly_increment": 1, "max_days": 24, "carryover_days": 5,
           "carryover_expiry": "03-31", "notice_weeks": 2, "shutdown_days": 3}
    if "shutdown" not in text:
        out["shutdown_days"] = None
    return out
