"""Exercise 6: SLIs, burn rate and multiwindow alerts over a day of traces."""

import pytest

import make_day
from mine import alerts_at, burn_rate, is_good
from obskit.slo import ALERT_RULES, DEFAULT_SLOS, MINUTE_MS, SLO, AlertRule, request_events
from obskit.slo import alerts_at as ref_alerts
from obskit.slo import burn_rate as ref_burn

AV = SLO("availability", "availability", 0.995)
LAT = SLO("latency", "latency", 0.95, 8000)
GR = SLO("grounded", "grounded", 0.97)
COST = SLO("cost", "cost", 0.99, 0.002)


def ev(t_min, error=False, dur=1000, grounded=True, cost=0.001):
    return {"trace_id": f"t{t_min}", "t_ms": t_min * MINUTE_MS, "duration_ms": dur, "error": error,
            "grounded": grounded, "cost_usd": cost}


def test_is_good_kinds():
    assert is_good(ev(0), AV) is True and is_good(ev(0, error=True), AV) is False
    assert is_good(ev(0, dur=9000), LAT) is False and is_good(ev(0, dur=8000), LAT) is True
    assert is_good(ev(0, error=True, dur=100), LAT) is None
    assert is_good(ev(0, grounded=None), GR) is None and is_good(ev(0, grounded=False), GR) is False
    assert is_good(ev(0, error=True), GR) is None
    assert is_good(ev(0, cost=0.003), COST) is False
    with pytest.raises(ValueError):
        is_good(ev(0), SLO("x", "nope", 0.9))


def test_burn_rate_arithmetic_and_window_edges():
    events = [ev(i, error=(i < 2)) for i in range(100)]          # minutes 0..99, 2 bad
    assert burn_rate(events, AV, 0, 100 * MINUTE_MS) == pytest.approx(4.0)
    assert burn_rate(events, AV, 2 * MINUTE_MS, 100 * MINUTE_MS) == 0.0   # start inclusive
    assert burn_rate(events, AV, 0, 1 * MINUTE_MS) == pytest.approx(200.0)  # end exclusive: only minute 0
    assert burn_rate([], AV, 0, 1) == 0.0
    assert burn_rate([ev(0, grounded=None)], GR, 0, MINUTE_MS) == 0.0   # nothing eligible


def test_alerts_need_both_windows():
    rule = AlertRule("page", 60, 5, 14.4)
    bad_long_ago = [ev(i, error=(i < 20)) for i in range(60)]     # errors only in minutes 0-19
    assert alerts_at(bad_long_ago, AV, 60 * MINUTE_MS, [rule]) == []   # short window is clean
    burning = [ev(i, error=(i >= 40)) for i in range(60)]          # last 20 minutes all bad
    out = alerts_at(burning, AV, 60 * MINUTE_MS, [rule])
    assert len(out) == 1 and out[0]["severity"] == "page" and out[0]["threshold"] == 14.4
    assert out[0]["long_burn"] == pytest.approx((20 / 60) / 0.005)
    assert out[0]["short_burn"] == pytest.approx(200.0)
    assert set(out[0]) == {"severity", "long_min", "short_min", "threshold", "long_burn", "short_burn"}


@pytest.fixture(scope="module")
def day():
    return request_events(make_day.generate(22))


def test_matches_reference_on_the_synthetic_day(day):
    start = day[0]["t_ms"] - day[0]["t_ms"] % (24 * 60 * MINUTE_MS)
    for slo in DEFAULT_SLOS:
        for h in (1, 4, 11.5, 12, 20):
            t = start + h * 60 * MINUTE_MS
            assert burn_rate(day, slo, t - 60 * MINUTE_MS, t) == pytest.approx(ref_burn(day, slo, t - 60 * MINUTE_MS, t))
            got, want = alerts_at(day, slo, t, ALERT_RULES), ref_alerts(day, slo, t, ALERT_RULES)
            assert len(got) == len(want), (slo.name, h)
            for g, w in zip(got, want):
                assert {k: g[k] for k in ("severity", "long_min", "short_min", "threshold")} == \
                       {k: w[k] for k in ("severity", "long_min", "short_min", "threshold")}
                assert g["long_burn"] == pytest.approx(w["long_burn"]) and g["short_burn"] == pytest.approx(w["short_burn"])
