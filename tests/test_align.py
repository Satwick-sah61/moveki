import pandas as pd
import pytest

from app.align import hourly_actuals
from app.data import to_utc


def _actuals(rows):
    return pd.DataFrame(
        {
            "start_time": to_utc([r[0] for r in rows]),
            "actual_mw": [float(r[1]) for r in rows],
        }
    )


def test_block_mean_averages_the_two_half_hours():
    df = _actuals(
        [
            ("2026-01-10T00:00Z", 100),
            ("2026-01-10T00:30Z", 300),
            ("2026-01-10T01:00Z", 500),
            ("2026-01-10T01:30Z", 700),
        ]
    )
    out = hourly_actuals(df, "block")
    assert out["start_time"].tolist() == [
        pd.Timestamp("2026-01-10T00:00Z"),
        pd.Timestamp("2026-01-10T01:00Z"),
    ]
    assert out["actual_mw"].tolist() == [200.0, 600.0]


def test_point_takes_the_period_starting_on_the_hour():
    df = _actuals(
        [
            ("2026-01-10T00:00Z", 100),
            ("2026-01-10T00:30Z", 300),
        ]
    )
    out = hourly_actuals(df, "point")
    assert out["actual_mw"].tolist() == [100.0]


def test_hour_with_a_missing_half_hour_is_dropped_not_guessed():
    df = _actuals(
        [
            ("2026-01-10T00:00Z", 100),
            ("2026-01-10T00:30Z", 300),
            ("2026-01-10T01:00Z", 500),  # 01:30 missing
        ]
    )
    out = hourly_actuals(df, "block")
    assert out["start_time"].tolist() == [pd.Timestamp("2026-01-10T00:00Z")]


def test_duplicated_half_hour_does_not_pass_as_a_complete_hour():
    df = _actuals(
        [
            ("2026-01-10T00:00Z", 100),
            ("2026-01-10T00:00Z", 300),  # duplicate :00, no :30
        ]
    )
    assert hourly_actuals(df, "block").empty


def test_unknown_method_is_rejected():
    with pytest.raises(ValueError):
        hourly_actuals(_actuals([("2026-01-10T00:00Z", 1)]), "median")  # type: ignore[arg-type]
