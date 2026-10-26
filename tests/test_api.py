"""Contract tests: each endpoint answers, validates its parameters and matches its schema."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_meta_describes_the_snapshot():
    res = client.get("/api/meta")
    assert res.status_code == 200
    body = res.json()
    assert body["scored_window"]["from"] == "2026-01-02"
    assert body["scored_window"]["to"] == "2026-02-01"
    assert body["scored_window"]["days"] == 31
    assert body["default_gate"] == "09:20"
    assert body["snapshot"]["scored_half_hours"] == 1488
    assert body["snapshot"]["runs_per_utc_day"] == {"8": 43}  # 21 Dec to 1 Feb, 8 runs every day
    assert "Cache-Control" in res.headers


def test_decision_replay_golden_day():
    res = client.get("/api/decision", params={"date": "2026-01-15", "gate": "09:20"})
    assert res.status_code == 200
    body = res.json()
    assert body["cutoff_utc"] == "2026-01-14T09:20:00Z"
    assert body["hours_total"] == 24 and body["hours_scored"] == 24
    assert [r["publish_time"] for r in body["runs_used"]] == ["2026-01-14T07:30:00Z"]
    first = body["hours"][0]
    assert first["start_time"] == "2026-01-15T00:00:00Z"
    assert first["lead_h"] == 16.5
    assert first["band_lo_mw"] < first["forecast_mw"]  # the band sits below a high-reading forecast
    assert all(run["publish_time"] > body["cutoff_utc"] for run in body["later_runs"])


def test_decision_replay_worst_day_is_flagged():
    body = client.get("/api/decision", params={"date": "2026-01-28"}).json()
    assert body["after_reveal"]["unusual_day"] is True
    assert body["after_reveal"]["net_gwh"] == pytest.approx(129.0, abs=0.1)


def test_decision_rejects_days_outside_the_window():
    assert client.get("/api/decision", params={"date": "2026-02-02"}).status_code == 422
    assert client.get("/api/decision", params={"date": "not-a-date"}).status_code == 422


def test_gate_parameter_is_validated():
    assert client.get("/api/scorecard", params={"gate": "9:20"}).status_code == 422
    assert client.get("/api/scorecard", params={"gate": "25:00"}).status_code == 422
    assert (
        client.get("/api/decision", params={"date": "2026-01-15", "gate": "nine"}).status_code
        == 422
    )


def test_align_parameter_is_validated():
    assert client.get("/api/scorecard", params={"align": "median"}).status_code == 422
    assert client.get("/api/scorecard", params={"align": "point"}).status_code == 200


def test_scorecard_headline_numbers():
    body = client.get("/api/scorecard", params={"gate": "09:20"}).json()
    k = body["kpis"]
    assert k["n"] == 744 and k["coverage"] == 1.0
    # Decision days 1-31 January (delivery 2 Jan - 1 Feb), block alignment, 09:20 gate.
    assert k["mae"] == pytest.approx(2039, abs=1)
    assert k["bias"] == pytest.approx(1748, abs=1)
    assert k["share_over"] == pytest.approx(0.85, abs=0.01)
    assert k["p90_abs"] == pytest.approx(4098, abs=1)
    assert k["wape"] == pytest.approx(0.181, abs=0.001)
    assert k["persistence_mae"] > k["mae"]  # the forecast beats persistence
    assert k["adjusted_mae"] < k["mae"]  # the no-leakage correction helps
    assert 0.7 <= k["band_coverage_oos"] <= 0.95
    assert len(body["daily"]) == 31 and len(body["worst_days"]) == 5
    assert body["worst_days"][0]["day"] == "2026-01-28"
    assert len(body["by_hour"]) == 24
    assert sum(b["n"] for b in body["histogram"]) == 744
    assert body["sentences"] and "high" in body["sentences"][0]


def test_timing_curve_covers_every_half_hour_and_the_presets():
    body = client.get("/api/timing").json()
    gates = [g["gate"] for g in body["gates"]]
    assert "09:20" in gates and "09:50" in gates and "15:30" in gates and "02:30" in gates
    by_gate = {g["gate"]: g for g in body["gates"]}
    assert by_gate["09:20"]["mae_mw"] == pytest.approx(2039, abs=1)
    assert by_gate["15:30"]["mae_mw"] < by_gate["09:50"]["mae_mw"] < by_gate["09:20"]["mae_mw"]
    assert by_gate["02:00"]["full_coverage"] is False and by_gate["02:00"]["coverage"] < 1
    assert by_gate["02:30"]["full_coverage"] is True and by_gate["02:30"]["coverage"] == 1
    assert body["headline"] and "15:30" in body["headline"]


def test_leadtime_buckets_have_counts_and_grow_with_lead():
    body = client.get("/api/leadtime").json()
    buckets = body["buckets"]
    assert buckets[0]["bucket"] == 0 and buckets[0]["n"] == 744
    assert buckets[-1]["mae_mw"] > buckets[0]["mae_mw"]
    assert body["decision_window_h"] == [16.5, 39.5]


def test_openapi_lists_every_endpoint():
    paths = client.get("/api/openapi.json").json()["paths"]
    assert set(paths) >= {
        "/api/health",
        "/api/meta",
        "/api/decision",
        "/api/scorecard",
        "/api/timing",
        "/api/leadtime",
    }


def test_decision_replay_at_an_early_gate_returns_gaps_not_an_error():
    # Before 02:30 on D-1 only runs from D-2 exist, which end at 21:00 on D: 22:00 and 23:00
    # are gaps and must come back as nulls, not crash the response.
    res = client.get("/api/decision", params={"date": "2026-01-15", "gate": "02:00"})
    assert res.status_code == 200
    body = res.json()
    assert body["hours_total"] == 24 and body["hours_with_forecast"] == 22
    gap = body["hours"][22]
    assert gap["publish_time"] is None and gap["forecast_mw"] is None and gap["lead_h"] is None
    assert body["hours"][0]["forecast_mw"] is not None


def test_window_edges_are_decision_days_in_january():
    # Decisions made 1-31 January deliver on 2 January to 1 February.
    assert client.get("/api/decision", params={"date": "2026-01-02"}).status_code == 200
    assert client.get("/api/decision", params={"date": "2026-02-01"}).status_code == 200
    assert client.get("/api/decision", params={"date": "2026-01-01"}).status_code == 422
    assert client.get("/api/decision", params={"date": "2026-02-02"}).status_code == 422


def test_waiting_block_reports_win_rates_and_hindsight():
    body = client.get("/api/waiting").json()
    assert body["baseline_gate"] == "09:20" and body["days"] == 31
    by_gate = {c["gate"]: c for c in body["comparisons"]}
    assert set(by_gate) == {"09:50", "15:30"}
    late = by_gate["15:30"]
    assert late["days_better"] + late["days_worse"] + late["days_same"] == 31
    assert (late["days_better"], late["days_worse"]) == (16, 15)
    assert late["mean_gain_mw"] == pytest.approx(165, abs=1)
    assert late["median_gain_mw"] < late["mean_gain_mw"]  # a few big days carry the average
    assert late["best_gain_day"] == "2026-01-28"
    runs = {r["run"]: r for r in body["runs"]}
    assert list(runs) == ["02:30", "04:30", "07:30", "09:30", "11:30", "15:30", "18:30", "22:30"]
    assert sum(r["best_days"] for r in body["runs"]) == 31
    assert runs["22:30"]["mean_mae_mw"] < runs["07:30"]["mean_mae_mw"]
    assert body["oracle_mae_mw"] < body["baseline_mae_mw"]
    assert body["oracle_improvement"] == pytest.approx(0.24, abs=0.01)
    assert body["baseline_mae_mw"] == pytest.approx(2039, abs=1)
    assert len(body["daily"]) == 31 and "hindsight" in body["note"].lower()
    assert any("hindsight" in s for s in body["sentences"])


def test_leadtime_reports_the_forecast_rows_about_past_hours():
    past = client.get("/api/leadtime").json()["past_hours"]
    assert past["share_of_rows"] == pytest.approx(0.2055, abs=0.001)
    assert past["hours_per_run_min"] == 6 and past["hours_per_run_max"] == 26
    # Even for hours that had already happened the forecast reads about 1.7 GW above the meter.
    assert past["bias_mw"] == pytest.approx(1666, abs=2)
    assert past["scored_n"] == 3697


def test_replay_exposes_the_mean_and_median_miss_separately():
    b = client.get("/api/decision", params={"date": "2026-01-28"}).json()["before_reveal"]
    assert b["month_mae_mw"] == pytest.approx(2039, abs=1)
    assert b["month_p50_abs_mw"] < b["month_mae_mw"]
