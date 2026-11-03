from hypothesis import given
from hypothesis import strategies as st

from solution import parse_vacation_policy

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def s(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def bullets(v):
    return [
        f"Full-time employees receive {v['first']} paid vacation days in their first year of employment.",
        f"From the second year, the allowance grows by {s(v['inc'], 'day')} per year of service, "
        f"up to a maximum of {v['max']} days.",
        "Part-time employees receive vacation days in proportion to their scope of employment.",
        f"Up to {v['carry']} unused days may be carried over to the next calendar year. "
        f"Carried-over days expire on {MONTHS[v['month'] - 1]} {v['day']}.",
        f"Vacation requests of 3 days or more must be submitted in the HR portal at least {s(v['notice'], 'week')} "
        "in advance and approved by the direct manager.",
        "During the company-wide shutdown week (between Rosh Hashanah and Yom Kippur), "
        f"{s(v['shut'], 'vacation day')} {'is' if v['shut'] == 1 else 'are'} deducted automatically.",
    ]


values = st.fixed_dictionaries({
    "first": st.integers(2, 40), "inc": st.integers(1, 3), "max": st.integers(10, 60),
    "carry": st.integers(2, 15), "month": st.integers(1, 12), "day": st.integers(1, 28),
    "notice": st.integers(1, 8), "shut": st.integers(1, 9),
})


def want(v):
    return {"first_year_days": v["first"], "yearly_increment": v["inc"], "max_days": v["max"],
            "carryover_days": v["carry"], "carryover_expiry": f"{v['month']:02d}-{v['day']:02d}",
            "notice_weeks": v["notice"], "shutdown_days": v["shut"]}


@given(values, st.permutations(range(6)))
def test_roundtrip_any_numbers_any_order(v, order):
    b = bullets(v)
    text = "# Vacation Policy (new version)\n\n" + "\n".join("- " + b[i] for i in order) + "\n"
    got, expected = parse_vacation_policy(text), want(v)
    diff = {k: (got.get(k), expected[k]) for k in expected if got.get(k) != expected[k]}
    assert not diff, f"wrong keys (got, expected): {diff} for values {v}"


DROPS = {0: ["first_year_days"], 1: ["yearly_increment", "max_days"], 3: ["carryover_days", "carryover_expiry"],
         4: ["notice_weeks"], 5: ["shutdown_days"]}


@given(values, st.sampled_from(sorted(DROPS)))
def test_missing_sentence_maps_to_none(v, drop):
    text = "\n".join("- " + line for i, line in enumerate(bullets(v)) if i != drop)
    got = parse_vacation_policy(text)
    bad = {k: got.get(k) for k in DROPS[drop] if got.get(k) is not None}
    assert set(got) == set(want(v)) and not bad, f"sentence {drop} removed, but got {bad or got}"
