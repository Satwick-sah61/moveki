"""Integrity of the committed data snapshot: what the analysis silently relies on."""

import hashlib

from app.data import DATA_DIR, load_actuals, load_forecasts, load_manifest


def _sha256(name: str) -> str:
    return hashlib.sha256((DATA_DIR / name).read_bytes()).hexdigest()


def test_csv_hashes_match_the_manifest():
    manifest = load_manifest()
    for name, info in manifest["files"].items():
        assert _sha256(name) == info["sha256"], f"{name} differs from the manifest"


def test_scored_window_has_every_half_hour_exactly_once():
    # Decisions made 1-31 January deliver on 2 January to 1 February: 31 days x 48 periods.
    actuals = load_actuals()
    scored = actuals[actuals["settlement_date"].between("2026-01-02", "2026-02-01")]
    assert len(scored) == 31 * 48
    assert scored["start_time"].is_unique
    assert set(scored.groupby("settlement_date").size()) == {48}
    assert load_manifest()["files"]["actuals_wind.csv"]["scored_half_hours"] == 31 * 48


def test_forecast_keys_are_unique_and_runs_are_regular():
    forecasts = load_forecasts()
    assert not forecasts.duplicated(["publish_time", "start_time"]).any()
    per_run = forecasts.groupby("publish_time").size()
    assert set(per_run) == {73}
    per_day = per_run.groupby(per_run.index.date).size()
    assert set(per_day) == {8}


def test_every_run_covers_the_same_fixed_window():
    forecasts = load_forecasts()
    first = forecasts.groupby("publish_time")["start_time"].min()
    last = forecasts.groupby("publish_time")["start_time"].max()
    # Published on UTC day P: covers P-1 21:00Z to P+2 21:00Z.
    assert ((first.index.normalize() - first).dt.total_seconds() == 3 * 3600).all()
    assert ((last - last.index.normalize()).dt.total_seconds() == 2 * 86400 + 21 * 3600).all()


def test_values_are_in_a_plausible_gb_range():
    assert load_forecasts()["forecast_mw"].between(0, 30_000).all()
    assert load_actuals()["actual_mw"].between(0, 30_000).all()
