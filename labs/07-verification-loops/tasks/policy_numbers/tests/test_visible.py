from solution import parse_vacation_policy

# The real policy, as in data/acme/hr_policies.md
POLICY = """# Vacation Policy (effective January 2026)

- Full-time employees receive 14 paid vacation days in their first year of employment.
- From the second year, the allowance grows by 1 day per year of service, up to a maximum of 24 days.
- Part-time employees receive vacation days in proportion to their scope of employment.
- Up to 5 unused days may be carried over to the next calendar year. Carried-over days expire on March 31.
- Vacation requests of 3 days or more must be submitted in the HR portal at least 2 weeks in advance and approved by the direct manager.
- During the company-wide shutdown week (between Rosh Hashanah and Yom Kippur), 3 vacation days are deducted automatically.
"""

KEYS = {"first_year_days", "yearly_increment", "max_days", "carryover_days", "carryover_expiry",
        "notice_weeks", "shutdown_days"}


def test_all_keys_present():
    assert set(parse_vacation_policy(POLICY)) == KEYS


def test_first_year():
    assert parse_vacation_policy(POLICY)["first_year_days"] == 14


def test_increment_and_max():
    d = parse_vacation_policy(POLICY)
    assert (d["yearly_increment"], d["max_days"]) == (1, 24)


def test_carryover():
    assert parse_vacation_policy(POLICY)["carryover_days"] == 5


def test_expiry_as_month_day():
    assert parse_vacation_policy(POLICY)["carryover_expiry"] == "03-31"


def test_notice_weeks():
    assert parse_vacation_policy(POLICY)["notice_weeks"] == 2


def test_shutdown():
    assert parse_vacation_policy(POLICY)["shutdown_days"] == 3


def test_missing_sentence_gives_none():
    text = "\n".join(line for line in POLICY.splitlines() if "shutdown" not in line)
    assert parse_vacation_policy(text)["shutdown_days"] is None
