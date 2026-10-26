from datetime import date, time

import pandas as pd
import pytest

from app.data import load_actuals
from app.timewin import delivery_hours_utc, format_london, gate_utc, local_date


def test_gate_in_january_is_gmt_so_equals_utc():
    assert gate_utc(date(2026, 1, 15), time(9, 20)) == pd.Timestamp("2026-01-14T09:20Z")


def test_gate_in_summer_is_bst_one_hour_behind_in_utc():
    assert gate_utc(date(2026, 7, 16), time(9, 20)) == pd.Timestamp("2026-07-15T08:20Z")


def test_gate_two_days_before():
    assert gate_utc(date(2026, 1, 15), time(9, 20), days_before=2) == pd.Timestamp(
        "2026-01-13T09:20Z"
    )


def test_gate_time_that_does_not_exist_on_the_spring_clock_change_is_refused():
    # 2026-03-29 01:00-01:59 UK never happens (clocks jump to 02:00 BST).
    with pytest.raises(ValueError, match="does not exist"):
        gate_utc(date(2026, 3, 30), time(1, 30))
    assert gate_utc(date(2026, 3, 30), time(2, 0)) == pd.Timestamp("2026-03-29T01:00Z")


def test_ambiguous_autumn_gate_takes_the_first_occurrence():
    # 2026-10-25 01:30 UK happens twice; the earlier (BST) one is the conservative cutoff.
    assert gate_utc(date(2026, 10, 26), time(1, 30)) == pd.Timestamp("2026-10-25T00:30Z")


def test_delivery_day_has_24_hours_in_january():
    hours = delivery_hours_utc(date(2026, 1, 15))
    assert len(hours) == 24
    assert hours.iloc[0] == pd.Timestamp("2026-01-15T00:00Z")
    assert hours.iloc[-1] == pd.Timestamp("2026-01-15T23:00Z")


def test_spring_clock_change_day_has_23_hours():
    hours = delivery_hours_utc(date(2026, 3, 29))
    assert len(hours) == 23
    assert hours.iloc[0] == pd.Timestamp("2026-03-29T00:00Z")
    assert hours.iloc[-1] == pd.Timestamp("2026-03-29T22:00Z")  # 23:00 BST


def test_autumn_clock_change_day_has_25_hours():
    hours = delivery_hours_utc(date(2026, 10, 25))
    assert len(hours) == 25
    assert hours.iloc[0] == pd.Timestamp("2026-10-24T23:00Z")  # 00:00 BST
    assert hours.iloc[-1] == pd.Timestamp("2026-10-25T23:00Z")  # 23:00 GMT


def test_local_date_matches_elexon_settlement_date_for_every_actual():
    actuals = load_actuals()
    assert (local_date(actuals["start_time"]) == actuals["settlement_date"]).all()


def test_format_london_shows_uk_time():
    assert format_london(pd.Timestamp("2026-07-15T08:20Z")) == "15 Jul 09:20"
    assert format_london(pd.Timestamp("2026-01-14T07:30Z")) == "14 Jan 07:30"
