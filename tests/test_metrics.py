"""Metric formulas checked on small hand-computed examples."""

import numpy as np
import pandas as pd
import pytest

from app import metrics
from app.data import to_utc


def test_error_stats_on_toy_numbers():
    err = pd.Series([1.0, -1.0, 3.0, np.nan, 5.0])  # NaN is ignored
    s = metrics.error_stats(err)
    assert s["n"] == 4
    assert s["mae"] == pytest.approx((1 + 1 + 3 + 5) / 4)
    assert s["rmse"] == pytest.approx(np.sqrt((1 + 1 + 9 + 25) / 4))
    assert s["bias"] == pytest.approx((1 - 1 + 3 + 5) / 4)
    assert s["share_over"] == pytest.approx(3 / 4)
    assert s["max_abs"] == 5.0
    assert s["p90_shortfall"] == pytest.approx(pd.Series([1.0, -1.0, 3.0, 5.0]).quantile(0.9))


def test_error_stats_empty():
    assert metrics.error_stats(pd.Series([np.nan])) == {"n": 0}


def test_wape_is_sum_abs_error_over_sum_actual():
    f = pd.Series([110.0, 90.0, np.nan])
    a = pd.Series([100.0, 100.0, 50.0])
    assert metrics.wape(f, a) == pytest.approx(20 / 200)
    assert metrics.wape(pd.Series([1.0]), pd.Series([0.0])) is None


def test_skill_is_one_minus_ratio():
    assert metrics.skill(50.0, 100.0) == pytest.approx(0.5)
    assert metrics.skill(100.0, 100.0) == pytest.approx(0.0)
    assert metrics.skill(None, 100.0) is None
    assert metrics.skill(50.0, 0.0) is None


def _scored(rows):
    df = pd.DataFrame(rows, columns=["day", "start_time", "forecast_mw", "actual_mw", "local_hour"])
    df["start_time"] = to_utc(df["start_time"])
    df["error_mw"] = df["forecast_mw"] - df["actual_mw"]
    return df


def test_daily_summary_net_energy_in_gwh():
    df = _scored(
        [
            ("2026-01-10", "2026-01-10T00:00Z", 1500.0, 1000.0, 0),
            ("2026-01-10", "2026-01-10T01:00Z", 500.0, 1000.0, 1),
            ("2026-01-11", "2026-01-11T00:00Z", 3000.0, 1000.0, 0),
        ]
    )
    d = metrics.daily_summary(df)
    assert d["day"].tolist() == ["2026-01-10", "2026-01-11"]
    assert d["hours"].tolist() == [2, 1]
    assert d["mae_mw"].tolist() == [500.0, 2000.0]
    assert d["bias_mw"].tolist() == [0.0, 2000.0]
    assert d["net_gwh"].tolist() == [0.0, 2.0]  # 2000 MW over one hour = 2 GWh


def test_flag_unusual_hours_and_days():
    rows = []
    for day in range(1, 11):
        for hour in range(3):
            rows.append(
                (f"2026-01-{day:02d}", f"2026-01-{day:02d}T{hour:02d}:00Z", 1000.0, 1000.0, hour)
            )
    df = _scored(rows)
    df.loc[0, "error_mw"] = 9000.0  # one wild hour on day 1
    df.loc[df["day"] == "2026-01-10", "error_mw"] = 5000.0  # one wild day
    daily = metrics.daily_summary(df)
    hours, days = metrics.flag_unusual(df, daily)
    assert hours.sum() >= 1 and hours.iloc[0]
    assert days.tolist()[-1] is True or bool(days.iloc[-1])
    assert int(days.sum()) == 1


def test_histogram_bins_cover_the_range():
    h = metrics.histogram(pd.Series([-600.0, -100.0, 100.0, 1200.0]), width_mw=500.0)
    assert h[0]["lo"] == -1000.0 and h[-1]["hi"] == 1500.0
    assert sum(b["n"] for b in h) == 4


def test_lead_bucket_floors_to_width():
    assert metrics.lead_bucket(pd.Series([0.0, 2.9, 3.0, 16.5, 39.5])).tolist() == [0, 0, 3, 15, 39]


def test_apply_band_uses_error_quantiles_with_the_right_sign():
    # error = forecast - actual, so actual = forecast - error.
    quantiles = pd.DataFrame(
        {"n": [100], "p10_err": [-200.0], "p90_err": [800.0]}, index=pd.Index([15], name="bucket")
    )
    sel = pd.DataFrame({"forecast_mw": [5000.0], "lead_h": [16.5]})
    out = metrics.apply_band(sel, quantiles)
    assert out.loc[0, "band_lo_mw"] == 5000.0 - 800.0
    assert out.loc[0, "band_hi_mw"] == 5000.0 + 200.0
    assert out.loc[0, "band_n"] == 100


def test_apply_band_without_a_matching_bucket_gives_no_band():
    quantiles = pd.DataFrame(
        {"n": [100], "p10_err": [-200.0], "p90_err": [800.0]}, index=pd.Index([15], name="bucket")
    )
    sel = pd.DataFrame({"forecast_mw": [5000.0], "lead_h": [50.0]})
    out = metrics.apply_band(sel, quantiles)
    assert pd.isna(out.loc[0, "band_lo_mw"]) and out.loc[0, "band_n"] == 0


def test_band_coverage_counts_hours_inside():
    df = pd.DataFrame(
        {
            "actual_mw": [100.0, 300.0, 50.0, np.nan],
            "band_lo_mw": [90.0, 90.0, 90.0, 0.0],
            "band_hi_mw": [200.0, 200.0, 200.0, 1.0],
        }
    )
    assert metrics.band_coverage(df) == pytest.approx(1 / 3)


def test_trailing_bias_uses_only_settled_prior_days():
    rows = []
    for day in range(1, 21):
        for hour in range(2):
            rows.append(
                (
                    f"2026-01-{day:02d}",
                    f"2026-01-{day:02d}T{hour:02d}:00Z",
                    1000.0 + day,
                    1000.0,
                    hour,
                )
            )
    df = _scored(rows)  # error on day d is exactly d
    tb = metrics.trailing_bias(df, min_hours=2)
    by_day = tb.groupby(df["day"]).first()
    # Day 15 uses days 7..13 -> mean error 10. Day 4's window (Dec 27..Jan 2) holds days 1 and 2
    # -> mean 1.5. Day 2's window ends on Dec 31, before any data: NaN.
    assert by_day["2026-01-15"] == pytest.approx(10.0)
    assert by_day["2026-01-04"] == pytest.approx(1.5)
    assert np.isnan(by_day["2026-01-02"])
    # Day 15's window excludes day 14 (D-1, not settled) and day 15 itself.
    assert by_day["2026-01-15"] != pytest.approx((7 + 8 + 9 + 10 + 11 + 12 + 13 + 14) / 8)


def test_paired_gain_counts_days_and_signs_on_toy_numbers():
    base = pd.Series({"d1": 100.0, "d2": 100.0, "d3": 100.0, "d4": 200.0})
    other = pd.Series({"d1": 60.0, "d2": 100.0, "d3": 130.0, "d4": 100.0, "d5": 1.0})
    g = metrics.paired_gain(base, other)
    assert g["days"] == 4  # d5 has no baseline and is ignored
    assert (g["days_better"], g["days_worse"], g["days_same"]) == (2, 1, 1)
    assert g["mean_gain"] == pytest.approx((40 + 0 - 30 + 100) / 4)
    assert g["median_gain"] == pytest.approx(20.0)
    assert g["mean_gain_pct"] == pytest.approx(27.5 / 125.0)
    assert (g["best_day"], g["best_gain"]) == ("d4", 100.0)
    assert (g["worst_day"], g["worst_gain"]) == ("d3", -30.0)


def test_paired_gain_with_no_common_days():
    assert metrics.paired_gain(pd.Series({"a": 1.0}), pd.Series({"b": 1.0})) == {"days": 0}
