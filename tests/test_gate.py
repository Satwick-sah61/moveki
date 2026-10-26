from datetime import date, time

import pandas as pd
import pytest

from app.data import load_actuals, load_forecasts, to_utc
from app.gate import latest_actual_at_cutoff, latest_actuals_at_cutoffs, latest_at_cutoff
from app.timewin import delivery_hours_utc, gate_utc

T = pd.Timestamp("2026-01-14T09:20Z")
TARGET = pd.Timestamp("2026-01-15T12:00Z")


def _forecasts(rows):
    return pd.DataFrame(
        {
            "publish_time": to_utc([r[0] for r in rows]),
            "start_time": to_utc([r[1] for r in rows]),
            "forecast_mw": [float(r[2]) for r in rows],
        }
    )


def _targets(hours, cutoff):
    return pd.DataFrame({"start_time": to_utc(hours), "cutoff": to_utc([cutoff] * len(hours))})


def test_takes_the_newest_run_published_before_the_cutoff():
    f = _forecasts(
        [
            ("2026-01-14T02:30Z", TARGET, 1000),
            ("2026-01-14T07:30Z", TARGET, 2000),
            ("2026-01-14T09:30Z", TARGET, 3000),  # after the gate: must not be used
        ]
    )
    out = latest_at_cutoff(f, _targets([TARGET], T))
    assert out.loc[0, "forecast_mw"] == 2000.0
    assert out.loc[0, "publish_time"] == pd.Timestamp("2026-01-14T07:30Z")
    assert out.loc[0, "lead_h"] == 28.5
    assert out.loc[0, "age_h"] == pytest.approx(1 + 50 / 60)  # 07:30 -> 09:20


def test_run_published_exactly_at_the_cutoff_counts():
    f = _forecasts([("2026-01-14T07:30Z", TARGET, 2000), (T, TARGET, 2500)])
    out = latest_at_cutoff(f, _targets([TARGET], T))
    assert out.loc[0, "forecast_mw"] == 2500.0


def test_run_published_one_minute_after_the_cutoff_is_ignored():
    f = _forecasts(
        [("2026-01-14T07:30Z", TARGET, 2000), (T + pd.Timedelta(minutes=1), TARGET, 2500)]
    )
    out = latest_at_cutoff(f, _targets([TARGET], T))
    assert out.loc[0, "forecast_mw"] == 2000.0


def test_missing_target_stays_missing():
    f = _forecasts([("2026-01-14T07:30Z", TARGET, 2000)])
    other = TARGET + pd.Timedelta(hours=1)
    out = latest_at_cutoff(f, _targets([TARGET, other], T))
    assert out.loc[0, "forecast_mw"] == 2000.0
    assert pd.isna(out.loc[1, "forecast_mw"])
    assert pd.isna(out.loc[1, "publish_time"])


def test_selection_is_per_target_hour_not_per_run():
    # A newer run that does not cover the second hour must not hide the older run's value.
    other = TARGET + pd.Timedelta(hours=1)
    f = _forecasts(
        [
            ("2026-01-14T02:30Z", TARGET, 1000),
            ("2026-01-14T02:30Z", other, 1100),
            ("2026-01-14T07:30Z", TARGET, 2000),
        ]
    )
    out = latest_at_cutoff(f, _targets([TARGET, other], T))
    assert out["forecast_mw"].tolist() == [2000.0, 1100.0]


def test_duplicate_key_keeps_the_last_value():
    f = _forecasts([("2026-01-14T07:30Z", TARGET, 2000), ("2026-01-14T07:30Z", TARGET, 2100)])
    out = latest_at_cutoff(f, _targets([TARGET], T))
    assert out.loc[0, "forecast_mw"] == 2100.0


def test_row_without_publish_time_is_never_available():
    f = _forecasts([("2026-01-14T07:30Z", TARGET, 2000)])
    f = pd.concat(
        [f, pd.DataFrame({"publish_time": [pd.NaT], "start_time": [TARGET], "forecast_mw": [9.0]})],
        ignore_index=True,
    )
    out = latest_at_cutoff(f, _targets([TARGET], T))
    assert out.loc[0, "forecast_mw"] == 2000.0


def _january_selection(gate: time, days_before: int = 1) -> pd.DataFrame:
    frames = []
    for day in range(1, 32):
        d = date(2026, 1, day)
        hours = delivery_hours_utc(d)
        cutoff = gate_utc(d, gate, days_before)
        frames.append(pd.DataFrame({"start_time": hours, "cutoff": cutoff, "day": d.isoformat()}))
    return latest_at_cutoff(load_forecasts(), pd.concat(frames, ignore_index=True))


def test_golden_day_15_jan_at_0920_uses_the_0730z_run():
    out = _january_selection(time(9, 20))
    day = out[out["day"] == "2026-01-15"]
    assert day["publish_time"].unique().tolist() == [pd.Timestamp("2026-01-14T07:30Z")]
    assert day["lead_h"].min() == 16.5
    assert day["lead_h"].max() == 39.5


def test_golden_day_15_jan_at_0950_uses_the_0930z_run():
    out = _january_selection(time(9, 50))
    day = out[out["day"] == "2026-01-15"]
    assert day["publish_time"].unique().tolist() == [pd.Timestamp("2026-01-14T09:30Z")]


def test_golden_day_15_jan_at_1530_uses_the_1530z_run_inclusive():
    out = _january_selection(time(15, 30))
    day = out[out["day"] == "2026-01-15"]
    assert day["publish_time"].unique().tolist() == [pd.Timestamp("2026-01-14T15:30Z")]
    assert day["lead_h"].min() == 8.5


def test_no_look_ahead_over_the_whole_snapshot():
    for gate in (time(2, 30), time(9, 20), time(9, 50), time(15, 30), time(23, 30)):
        out = _january_selection(gate)
        assert (out["publish_time"] <= out["cutoff"]).all()
        assert (out["lead_h"] > 0).all()


def test_full_coverage_at_the_default_gate():
    out = _january_selection(time(9, 20))
    assert len(out) == 31 * 24
    assert out["forecast_mw"].notna().all()


def test_early_gates_cannot_cover_the_last_two_hours_of_the_day():
    # Every run covers a fixed 21:00-to-21:00 window, so a 01:00 gate on D-1 only sees runs
    # published on D-2, which end at 21:00 on D. 22:00 and 23:00 are therefore gaps.
    out = _january_selection(time(1, 0))
    missing = out[out["forecast_mw"].isna()]
    assert len(missing) == 31 * 2
    assert set(missing["start_time"].dt.hour) == {22, 23}


def test_persistence_uses_the_last_actual_published_by_the_cutoff():
    actuals = load_actuals()
    cutoff = pd.Timestamp("2026-01-14T09:20Z")
    value = latest_actual_at_cutoff(actuals, cutoff)
    # The 08:30-09:00 period is published at 09:00; 09:00-09:30 only at 09:30, so not yet.
    expected = actuals.loc[actuals["start_time"] == pd.Timestamp("2026-01-14T08:30Z"), "actual_mw"]
    assert value == float(expected.iloc[0])


def test_vectorised_persistence_matches_the_scalar_rule():
    actuals = load_actuals()
    cutoffs = pd.Series(
        [
            pd.Timestamp("2026-01-14T09:20Z"),
            pd.Timestamp("2026-01-20T15:30Z"),
            pd.Timestamp("2025-12-01T00:00Z"),
            pd.Timestamp("2026-02-05T00:00Z"),
        ]
    )
    vec = latest_actuals_at_cutoffs(actuals, cutoffs)
    for i, c in cutoffs.items():
        scalar = latest_actual_at_cutoff(actuals, c)
        assert (scalar is None and pd.isna(vec[i])) or scalar == vec[i]


def test_persistence_before_any_data_is_none():
    actuals = load_actuals()
    assert latest_actual_at_cutoff(actuals, pd.Timestamp("2025-12-01T00:00Z")) is None
