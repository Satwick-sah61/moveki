// Hand-written mirror of app/schemas.py (the Pydantic response models). Keep the two in step;
// /api/docs shows the authoritative shapes.

export type Alignment = "block" | "point";

export interface Health {
  status: "ok";
  app: string;
  version: string;
}

export interface GatePreset {
  id: string;
  label: string;
  gate: string;
  default: boolean;
}

export interface Meta {
  app: string;
  version: string;
  scored_window: { from: string; to: string; days: number; oos_split: string; note: string };
  warmup_from: string;
  gate_presets: GatePreset[];
  default_gate: string;
  earliest_full_gate: string;
  alignment_methods: string[];
  snapshot: {
    fetched_at_utc: string;
    sources: Record<string, { url: string; raw_rows: number }>;
    files: Record<string, { sha256: string; bytes: number; rows: number }>;
    runs: number;
    runs_per_utc_day: Record<string, number>;
    publish_clock_times_utc: Record<string, number>;
    scored_half_hours: number;
    warnings: string[];
  };
}

export interface RunUsed {
  publish_time: string;
  hours: number;
  lead_min: number;
  lead_max: number;
  age_h: number;
}

export interface ReplayHour {
  start_time: string;
  local_hour: number;
  cutoff: string;
  publish_time: string | null;
  forecast_mw: number | null;
  lead_h: number | null;
  age_h: number | null;
  band_lo_mw: number | null;
  band_hi_mw: number | null;
  band_n: number;
  actual_mw: number | null;
  error_mw: number | null;
  persistence_mw: number | null;
  adjusted_mw: number | null;
  unusual_hour: boolean;
}

export interface LaterRun {
  publish_time: string;
  values: { start_time: string; forecast_mw: number | null }[];
}

export interface Replay {
  day: string;
  gate: string;
  cutoff_utc: string;
  alignment: Alignment;
  hours_total: number;
  hours_with_forecast: number;
  hours_scored: number;
  runs_used: RunUsed[];
  before_reveal: {
    forecast_energy_gwh: number | null;
    band_energy_lo_gwh: number | null;
    band_energy_hi_gwh: number | null;
    forecast_peak_mw: number | null;
    forecast_trough_mw: number | null;
    month_mae_mw: number | null;
    month_p50_abs_mw: number | null;
    month_p90_abs_mw: number | null;
    month_bias_mw: number | null;
    trailing_bias_mw: number | null;
    adjusted_energy_gwh: number | null;
  };
  after_reveal: {
    actual_energy_gwh: number | null;
    mae_mw: number | null;
    bias_mw: number | null;
    net_gwh: number | null;
    persistence_mae_mw: number | null;
    adjusted_mae_mw: number | null;
    unusual_day: boolean;
    band_hits: number;
  };
  hours: ReplayHour[];
  later_runs: LaterRun[];
}

export interface Kpis {
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  share_over: number | null;
  p50_abs: number | null;
  p90_abs: number | null;
  p95_abs: number | null;
  max_abs: number | null;
  p90_shortfall: number | null;
  hours_expected: number;
  coverage: number | null;
  wape: number | null;
  max_abs_at: string | null;
  persistence_mae: number | null;
  skill_vs_persistence: number | null;
  adjusted_mae: number | null;
  adjusted_bias: number | null;
  adjusted_p90_abs: number | null;
  adjusted_improvement: number | null;
  band_coverage_oos: number | null;
  mean_daily_net_gwh: number | null;
  alignment_other_mae: number | null;
  unusual_hour_threshold_mw: number | null;
  unusual_hours: number;
  unusual_days: number;
}

export interface DailyRow {
  day: string;
  hours: number;
  mae_mw: number | null;
  bias_mw: number | null;
  net_gwh: number | null;
  unusual: boolean;
}

export interface HourOfDayRow {
  hour: number;
  n: number;
  bias_mw: number | null;
  mae_mw: number | null;
}

export interface HistogramBin {
  lo: number;
  hi: number;
  n: number;
}

export interface WorstHour {
  start_time: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  error_mw: number | null;
  lead_h: number | null;
}

export interface Scorecard {
  gate: string;
  alignment: Alignment;
  days: number;
  kpis: Kpis;
  daily: DailyRow[];
  worst_days: DailyRow[];
  by_hour: HourOfDayRow[];
  histogram: HistogramBin[];
  worst_hours: WorstHour[];
  sentences: string[];
}

export interface TimingGate {
  gate: string;
  full_coverage: boolean;
  hours_scored: number;
  coverage: number | null;
  mae_mw: number | null;
  p90_abs_mw: number | null;
  bias_mw: number | null;
}

export interface Timing {
  alignment: Alignment;
  gates: TimingGate[];
  presets: GatePreset[];
  run_publish_times_utc: string[];
  earliest_full_gate: string;
  headline: string | null;
}

export interface LeadBucket {
  bucket: number;
  n: number;
  mae_mw: number | null;
  bias_mw: number | null;
  p10_err: number | null;
  p90_err: number | null;
}

export interface PastHours {
  rows_total: number;
  rows_past: number;
  share_of_rows: number | null;
  hours_per_run_min: number;
  hours_per_run_max: number;
  scored_n: number;
  mae_mw: number | null;
  bias_mw: number | null;
}

export interface WaitComparison {
  gate: string;
  label: string;
  baseline_gate: string;
  days: number;
  days_better: number;
  days_worse: number;
  days_same: number;
  mean_gain_mw: number | null;
  median_gain_mw: number | null;
  mean_gain_pct: number | null;
  best_gain_mw: number | null;
  best_gain_day: string;
  worst_gain_mw: number | null;
  worst_gain_day: string;
}

export interface RunScore {
  run: string;
  mean_mae_mw: number | null;
  best_days: number;
  worst_days: number;
}

export interface WaitDay {
  day: string;
  mae_baseline_mw: number | null;
  mae_waited_mw: number | null;
  gain_mw: number | null;
  best_run: string;
  best_mae_mw: number | null;
}

export interface Waiting {
  alignment: Alignment;
  baseline_gate: string;
  days: number;
  baseline_mae_mw: number | null;
  comparisons: WaitComparison[];
  runs: RunScore[];
  oracle_mae_mw: number | null;
  oracle_improvement: number | null;
  latest_run: string;
  daily: WaitDay[];
  sentences: string[];
  note: string;
}

export interface LeadTime {
  alignment: Alignment;
  bucket_hours: number;
  buckets: LeadBucket[];
  past_hours: PastHours;
  decision_window_h: [number | null, number | null];
  note: string;
}
