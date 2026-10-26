"""Pydantic v2 response models. They define the API contract (OpenAPI at /api/docs) and the
shapes the TypeScript front end mirrors by hand in frontend/src/types.ts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Alignment = Literal["block", "point"]


class Health(BaseModel):
    status: Literal["ok"]
    app: str
    version: str


class GatePreset(BaseModel):
    id: str
    label: str
    gate: str = Field(description="HH:MM UK local time on the day before delivery")
    default: bool


class ScoredWindow(BaseModel):
    from_: str = Field(alias="from")
    to: str
    days: int
    oos_split: str
    note: str

    model_config = {"populate_by_name": True}


class SnapshotFile(BaseModel):
    sha256: str
    bytes: int
    rows: int


class Snapshot(BaseModel):
    fetched_at_utc: str
    sources: dict[str, dict[str, Any]]
    files: dict[str, SnapshotFile]
    runs: int
    runs_per_utc_day: dict[str, int]
    publish_clock_times_utc: dict[str, int]
    scored_half_hours: int
    warnings: list[str]


class Meta(BaseModel):
    app: str
    version: str
    scored_window: ScoredWindow
    warmup_from: str
    gate_presets: list[GatePreset]
    default_gate: str
    earliest_full_gate: str
    alignment_methods: list[str]
    snapshot: Snapshot


class RunUsed(BaseModel):
    publish_time: str
    hours: int
    lead_min: float
    lead_max: float
    age_h: float


class ReplayHour(BaseModel):
    start_time: str
    local_hour: int
    cutoff: str
    publish_time: str | None
    forecast_mw: float | None
    lead_h: float | None
    age_h: float | None
    band_lo_mw: float | None
    band_hi_mw: float | None
    band_n: int
    actual_mw: float | None
    error_mw: float | None
    persistence_mw: float | None
    adjusted_mw: float | None
    unusual_hour: bool


class RunValue(BaseModel):
    start_time: str
    forecast_mw: float | None


class LaterRun(BaseModel):
    publish_time: str
    values: list[RunValue]


class BeforeReveal(BaseModel):
    forecast_energy_gwh: float | None
    band_energy_lo_gwh: float | None
    band_energy_hi_gwh: float | None
    forecast_peak_mw: float | None
    forecast_trough_mw: float | None
    month_mae_mw: float | None
    month_p50_abs_mw: float | None
    month_p90_abs_mw: float | None
    month_bias_mw: float | None
    trailing_bias_mw: float | None
    adjusted_energy_gwh: float | None


class AfterReveal(BaseModel):
    actual_energy_gwh: float | None
    mae_mw: float | None
    bias_mw: float | None
    net_gwh: float | None
    persistence_mae_mw: float | None
    adjusted_mae_mw: float | None
    unusual_day: bool
    band_hits: int


class Replay(BaseModel):
    day: str
    gate: str
    cutoff_utc: str
    alignment: Alignment
    hours_total: int
    hours_with_forecast: int
    hours_scored: int
    runs_used: list[RunUsed]
    before_reveal: BeforeReveal
    after_reveal: AfterReveal
    hours: list[ReplayHour]
    later_runs: list[LaterRun]


class Kpis(BaseModel):
    n: int
    mae: float | None = None
    rmse: float | None = None
    bias: float | None = None
    share_over: float | None = None
    p50_abs: float | None = None
    p90_abs: float | None = None
    p95_abs: float | None = None
    max_abs: float | None = None
    p90_shortfall: float | None = None
    hours_expected: int
    coverage: float | None
    wape: float | None
    max_abs_at: str | None
    persistence_mae: float | None
    skill_vs_persistence: float | None
    adjusted_mae: float | None
    adjusted_bias: float | None
    adjusted_p90_abs: float | None
    adjusted_improvement: float | None
    band_coverage_oos: float | None
    mean_daily_net_gwh: float | None
    alignment_other_mae: float | None
    unusual_hour_threshold_mw: float | None
    unusual_hours: int
    unusual_days: int


class DailyRow(BaseModel):
    day: str
    hours: int
    mae_mw: float | None
    bias_mw: float | None
    net_gwh: float | None
    unusual: bool


class HourOfDayRow(BaseModel):
    hour: int
    n: int
    bias_mw: float | None
    mae_mw: float | None


class HistogramBin(BaseModel):
    lo: float
    hi: float
    n: int


class WorstHour(BaseModel):
    start_time: str
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None
    lead_h: float | None


class Scorecard(BaseModel):
    gate: str
    alignment: Alignment
    days: int
    kpis: Kpis
    daily: list[DailyRow]
    worst_days: list[DailyRow]
    by_hour: list[HourOfDayRow]
    histogram: list[HistogramBin]
    worst_hours: list[WorstHour]
    sentences: list[str]


class TimingGate(BaseModel):
    gate: str
    full_coverage: bool
    hours_scored: int
    coverage: float | None
    mae_mw: float | None
    p90_abs_mw: float | None
    bias_mw: float | None


class Timing(BaseModel):
    alignment: Alignment
    gates: list[TimingGate]
    presets: list[GatePreset]
    run_publish_times_utc: list[str]
    earliest_full_gate: str
    headline: str | None


class LeadBucket(BaseModel):
    bucket: int
    n: int
    mae_mw: float | None
    bias_mw: float | None
    p10_err: float | None
    p90_err: float | None


class PastHours(BaseModel):
    rows_total: int
    rows_past: int
    share_of_rows: float | None
    hours_per_run_min: int
    hours_per_run_max: int
    scored_n: int
    mae_mw: float | None
    bias_mw: float | None


class LeadTime(BaseModel):
    alignment: Alignment
    bucket_hours: int
    buckets: list[LeadBucket]
    past_hours: PastHours
    decision_window_h: list[float | None]
    note: str


class WaitComparison(BaseModel):
    gate: str
    label: str
    baseline_gate: str
    days: int
    days_better: int
    days_worse: int
    days_same: int
    mean_gain_mw: float | None
    median_gain_mw: float | None
    mean_gain_pct: float | None
    best_gain_mw: float | None
    best_gain_day: str
    worst_gain_mw: float | None
    worst_gain_day: str


class RunScore(BaseModel):
    run: str
    mean_mae_mw: float | None
    best_days: int
    worst_days: int


class WaitDay(BaseModel):
    day: str
    mae_baseline_mw: float | None
    mae_waited_mw: float | None
    gain_mw: float | None
    best_run: str
    best_mae_mw: float | None


class Waiting(BaseModel):
    alignment: Alignment
    baseline_gate: str
    days: int
    baseline_mae_mw: float | None
    comparisons: list[WaitComparison]
    runs: list[RunScore]
    oracle_mae_mw: float | None
    oracle_improvement: float | None
    latest_run: str
    daily: list[WaitDay]
    sentences: list[str]
    note: str
