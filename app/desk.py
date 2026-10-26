"""Service layer: composes the data, the gate rule, alignment and metrics into the results
the API serves. Every result is a function of (gate, options) over an immutable snapshot, so
each is computed once per process and cached.
"""

from __future__ import annotations

from datetime import date, time, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from app import __version__, align, data, metrics, timewin
from app import gate as gatemod

# The brief scopes the data to "purchase decisions to be made in January 2026": decisions dated
# 1-31 January, which deliver power on 2 January to 1 February.
SCORED_FROM = date(2026, 1, 2)
SCORED_TO = date(2026, 2, 1)  # inclusive
# Earlier delivery days feed only the persistence baseline and the trailing bias adjustment.
WARMUP_FROM = date(2025, 12, 24)
DELIVERY_DAYS = [WARMUP_FROM + timedelta(days=i) for i in range((SCORED_TO - WARMUP_FROM).days + 1)]
SCORED_DAYS = [d for d in DELIVERY_DAYS if SCORED_FROM <= d <= SCORED_TO]

GATE_PRESETS = [
    {"id": "epex60", "label": "EPEX 60-min day-ahead auction", "gate": "09:20", "default": True},
    {"id": "n2ex", "label": "N2EX day-ahead auction", "gate": "09:50", "default": False},
    {"id": "epex30", "label": "EPEX 30-min day-ahead auction", "gate": "15:30", "default": False},
]
# Every WINDFOR run covers a fixed 21:00-to-21:00 window, so a gate before the first run of
# D-1 (02:30 UTC) only sees runs from D-2, which end at 21:00 on D: 22:00 and 23:00 are gaps.
EARLIEST_FULL_GATE = time(2, 30)
# Every half hour on D-1, plus the preset gates so they appear on the same curve.
TIMING_GATES = sorted(
    {time(h, m) for h in range(24) for m in (0, 30)} | {time(9, 20), time(9, 50), time(15, 30)}
)
OOS_SPLIT = date(2026, 1, 17)  # bands calibrated on days before this, tested from it on


def parse_gate(text: str) -> time:
    try:
        hh, mm = text.split(":")
        return time(int(hh), int(mm))
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"gate must be HH:MM, got {text!r}") from exc


def fmt_gate(t: time) -> str:
    return t.strftime("%H:%M")


# ---------------------------------------------------------------- frames


@lru_cache(maxsize=4)
def hourly_actuals(method: align.Method = "block") -> pd.DataFrame:
    return align.hourly_actuals(data.load_actuals(), method)


@lru_cache(maxsize=2)
def _delivery_hours() -> pd.DataFrame:
    """day + hourly start_time for every delivery day; the same for every gate."""
    frames = [
        pd.DataFrame({"day": d.isoformat(), "start_time": timewin.delivery_hours_utc(d)})
        for d in DELIVERY_DAYS
    ]
    return pd.concat(frames, ignore_index=True)


@lru_cache(maxsize=256)
def scored_frame(
    gate: time, days_before: int = 1, method: align.Method = "block", extras: bool = True
) -> pd.DataFrame:
    """One row per delivery hour (warm-up days included) with the forecast the desk could see
    and the actual. With extras, also the persistence baseline and the trailing-bias-adjusted
    forecast (the timing curve skips them: it only needs the error)."""
    cutoffs = {d.isoformat(): timewin.gate_utc(d, gate, days_before) for d in DELIVERY_DAYS}
    targets = _delivery_hours().copy()
    targets["cutoff"] = data.to_utc(targets["day"].map(cutoffs))
    sel = gatemod.latest_at_cutoff(data.load_forecasts(), targets)
    sel = sel.merge(hourly_actuals(method), on="start_time", how="left")
    sel["local_hour"] = sel["start_time"].dt.tz_convert(timewin.LONDON).dt.hour
    sel["error_mw"] = sel["forecast_mw"] - sel["actual_mw"]
    sel["in_scope"] = sel["day"].between(SCORED_FROM.isoformat(), SCORED_TO.isoformat())
    if not extras:
        return sel

    day_cutoffs = pd.Series(cutoffs)
    persistence = gatemod.latest_actuals_at_cutoffs(data.load_actuals(), day_cutoffs)
    sel["persistence_mw"] = sel["day"].map(persistence).astype("float64")
    sel["persistence_error_mw"] = sel["persistence_mw"] - sel["actual_mw"]

    sel["trailing_bias_mw"] = metrics.trailing_bias(sel)
    sel["adjusted_mw"] = sel["forecast_mw"] - sel["trailing_bias_mw"]
    sel["adjusted_error_mw"] = sel["adjusted_mw"] - sel["actual_mw"]
    return sel


def january(
    gate: time, days_before: int = 1, method: align.Method = "block", extras: bool = True
) -> pd.DataFrame:
    sf = scored_frame(gate, days_before, method, extras)
    return sf[sf["in_scope"]].reset_index(drop=True)


@lru_cache(maxsize=4)
def pairs_frame(method: align.Method = "block") -> pd.DataFrame:
    """Every (run, target) pair with a January target and lead >= 0, with its error. This is the
    sample the lead-time curve and the empirical bands are built from."""
    f = data.load_forecasts()
    df = f.merge(hourly_actuals(method), on="start_time", how="inner")
    df["day"] = timewin.local_date(df["start_time"])
    df = df[df["day"].between(SCORED_FROM.isoformat(), SCORED_TO.isoformat())]
    df["lead_h"] = (df["start_time"] - df["publish_time"]).dt.total_seconds() / 3600
    df = df[df["lead_h"] >= 0]
    df["error_mw"] = df["forecast_mw"] - df["actual_mw"]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- helpers


def _ts(x) -> str | None:
    if x is None or pd.isna(x):
        return None
    return pd.Timestamp(x).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(x, digits: int | None = None) -> float | None:
    if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x):
        return None
    v = float(x)
    return round(v, digits) if digits is not None else v


def _records(df: pd.DataFrame) -> list[dict]:
    out = []
    for row in df.to_dict("records"):
        clean = {}
        for k, v in row.items():
            if isinstance(v, pd.Timestamp) or v is pd.NaT:
                clean[k] = _ts(v)  # NaT (an hour with no eligible run) becomes null
            elif isinstance(v, (np.floating, float)):
                clean[k] = _num(v)
            elif isinstance(v, (np.integer,)):
                clean[k] = int(v)
            elif isinstance(v, (np.bool_,)):
                clean[k] = bool(v)
            else:
                clean[k] = v
        out.append(clean)
    return out


def _stats(err: pd.Series) -> dict:
    return {k: _num(v) if k != "n" else v for k, v in metrics.error_stats(err).items()}


# ---------------------------------------------------------------- results


def replay(day: date, gate: time, method: align.Method = "block") -> dict:
    """Decision Replay for one delivery day: what the desk could see at the gate, the band around
    it, the later runs, and (for the Reveal toggle) what actually happened."""
    if not (SCORED_FROM <= day <= SCORED_TO):
        raise ValueError(f"day must be between {SCORED_FROM} and {SCORED_TO}")
    sf = scored_frame(gate, 1, method)
    sel = sf[sf["day"] == day.isoformat()].reset_index(drop=True)
    cutoff = timewin.gate_utc(day, gate)

    quantiles = metrics.error_quantiles_by_bucket(pairs_frame(method), exclude_day=day.isoformat())
    sel = metrics.apply_band(sel, quantiles)

    month = january(gate, 1, method)
    month_stats = metrics.error_stats(month["error_mw"])
    hour_threshold = month["error_mw"].abs().quantile(0.95)
    daily = metrics.daily_summary(month)
    _, unusual_days = metrics.flag_unusual(month, daily)
    daily["unusual"] = unusual_days.values
    day_row = daily[daily["day"] == day.isoformat()]

    runs_used = (
        sel.dropna(subset=["publish_time"])
        .groupby("publish_time")
        .agg(
            hours=("start_time", "size"),
            lead_min=("lead_h", "min"),
            lead_max=("lead_h", "max"),
            age_h=("age_h", "first"),
        )
        .reset_index()
    )
    later = gatemod.runs_covering(data.load_forecasts(), sel["start_time"])
    later = later[later["publish_time"] > cutoff]
    later_runs = [
        {
            "publish_time": _ts(pub),
            "values": [
                {"start_time": _ts(r.start_time), "forecast_mw": _num(r.forecast_mw)}
                for r in grp.itertuples()
            ],
        }
        for pub, grp in later.groupby("publish_time")
    ]

    hours = sel.assign(unusual_hour=sel["error_mw"].abs() >= hour_threshold)[
        [
            "start_time",
            "local_hour",
            "cutoff",
            "publish_time",
            "forecast_mw",
            "lead_h",
            "age_h",
            "band_lo_mw",
            "band_hi_mw",
            "band_n",
            "actual_mw",
            "error_mw",
            "persistence_mw",
            "adjusted_mw",
            "unusual_hour",
        ]
    ]
    scored = sel.dropna(subset=["error_mw"])
    covered = sel.dropna(subset=["forecast_mw"])
    return {
        "day": day.isoformat(),
        "gate": fmt_gate(gate),
        "cutoff_utc": _ts(cutoff),
        "alignment": method,
        "hours_total": int(len(sel)),
        "hours_with_forecast": int(len(covered)),
        "hours_scored": int(len(scored)),
        "runs_used": _records(runs_used),
        "before_reveal": {
            "forecast_energy_gwh": _num(covered["forecast_mw"].sum() / 1000, 1),
            "band_energy_lo_gwh": _num(covered["band_lo_mw"].sum() / 1000, 1),
            "band_energy_hi_gwh": _num(covered["band_hi_mw"].sum() / 1000, 1),
            "forecast_peak_mw": _num(covered["forecast_mw"].max()),
            "forecast_trough_mw": _num(covered["forecast_mw"].min()),
            "month_mae_mw": _num(month_stats.get("mae")),
            "month_p50_abs_mw": _num(month_stats.get("p50_abs")),
            "month_p90_abs_mw": _num(month_stats.get("p90_abs")),
            "month_bias_mw": _num(month_stats.get("bias")),
            "trailing_bias_mw": _num(sel["trailing_bias_mw"].iloc[0]) if len(sel) else None,
            "adjusted_energy_gwh": _num(covered["adjusted_mw"].sum() / 1000, 1),
        },
        "after_reveal": {
            "actual_energy_gwh": _num(scored["actual_mw"].sum() / 1000, 1),
            "mae_mw": _num(scored["error_mw"].abs().mean()),
            "bias_mw": _num(scored["error_mw"].mean()),
            "net_gwh": _num(scored["error_mw"].sum() / 1000, 1),
            "persistence_mae_mw": _num(scored["persistence_error_mw"].abs().mean()),
            "adjusted_mae_mw": _num(scored["adjusted_error_mw"].abs().mean()),
            "unusual_day": bool(day_row["unusual"].iloc[0]) if len(day_row) else False,
            "band_hits": int(
                (
                    (scored["actual_mw"] >= scored["band_lo_mw"])
                    & (scored["actual_mw"] <= scored["band_hi_mw"])
                ).sum()
            ),
        },
        "hours": _records(hours),
        "later_runs": later_runs,
    }


def scorecard(gate: time, method: align.Method = "block") -> dict:
    """The same gate policy applied to every January day."""
    month = january(gate, 1, method)
    scored = month.dropna(subset=["error_mw"])
    stats = metrics.error_stats(month["error_mw"])
    persistence_stats = metrics.error_stats(month["persistence_error_mw"])
    adjusted_stats = metrics.error_stats(month["adjusted_error_mw"])

    daily = metrics.daily_summary(month)
    unusual_hours, unusual_days = metrics.flag_unusual(month, daily)
    daily["unusual"] = unusual_days.values
    worst = daily.reindex(daily["net_gwh"].abs().sort_values(ascending=False).index).head(5)

    # Out-of-sample band check: quantiles from the first half of the month, tested on the second.
    pairs = pairs_frame(method)
    calib = pairs[pairs["day"] < OOS_SPLIT.isoformat()]
    quantiles = metrics.error_quantiles_by_bucket(calib)
    test = month[month["day"] >= OOS_SPLIT.isoformat()]
    coverage_oos = metrics.band_coverage(metrics.apply_band(test, quantiles))

    # Alignment sensitivity: the same gate scored with point-matched actuals.
    other = "point" if method == "block" else "block"
    other_mae = metrics.error_stats(january(gate, 1, other)["error_mw"]).get("mae")

    max_row = scored.loc[scored["error_mw"].abs().idxmax()] if len(scored) else None
    worst_hours = scored.reindex(scored["error_mw"].abs().sort_values(ascending=False).index).head(
        10
    )

    kpis = {
        **_stats(month["error_mw"]),
        "hours_expected": int(len(month)),
        "coverage": _num(stats.get("n", 0) / len(month)) if len(month) else None,
        "wape": _num(metrics.wape(month["forecast_mw"], month["actual_mw"])),
        "max_abs_at": _ts(max_row["start_time"]) if max_row is not None else None,
        "persistence_mae": _num(persistence_stats.get("mae")),
        "skill_vs_persistence": _num(metrics.skill(stats.get("mae"), persistence_stats.get("mae"))),
        "adjusted_mae": _num(adjusted_stats.get("mae")),
        "adjusted_bias": _num(adjusted_stats.get("bias")),
        "adjusted_p90_abs": _num(adjusted_stats.get("p90_abs")),
        "adjusted_improvement": _num(metrics.skill(adjusted_stats.get("mae"), stats.get("mae"))),
        "band_coverage_oos": _num(coverage_oos),
        "mean_daily_net_gwh": _num(daily["net_gwh"].mean(), 1),
        "alignment_other_mae": _num(other_mae),
        "unusual_hour_threshold_mw": _num(month["error_mw"].abs().quantile(0.95)),
        "unusual_hours": int(unusual_hours.sum()),
        "unusual_days": int(unusual_days.sum()),
    }
    return {
        "gate": fmt_gate(gate),
        "alignment": method,
        "days": len(SCORED_DAYS),
        "kpis": kpis,
        "daily": _records(daily),
        "worst_days": _records(worst),
        "by_hour": _records(metrics.by_hour_of_day(month)),
        "histogram": metrics.histogram(month["error_mw"]),
        "worst_hours": _records(
            worst_hours[["start_time", "forecast_mw", "actual_mw", "error_mw", "lead_h"]]
        ),
        "sentences": buying_sentences(kpis),
    }


def buying_sentences(k: dict) -> list[str]:
    """Plain-language guidance generated from the numbers, so it cannot invent figures."""
    s = []
    gw = lambda mw: f"{mw / 1000:.2f} GW"  # noqa: E731
    bias = k.get("bias")
    if bias is not None:
        high = bias > 0
        s.append(
            f"At this gate the forecast read about {gw(abs(bias))} {'high' if high else 'low'} "
            f"on average, {'high' if high else 'low'} in {k['share_over'] * 100:.0f}% of hours: "
            f"shade wind expectations {'down' if high else 'up'} before you buy."
        )
    if k.get("p90_shortfall") is not None:
        s.append(
            f"Planning on {gw(k['p90_shortfall'])} less wind than forecast would have covered the "
            f"shortfall 9 hours in 10; the typical miss was {gw(k['mae'])} and 9 hours in 10 it "
            f"stayed under {gw(k['p90_abs'])}."
        )
    net = k.get("mean_daily_net_gwh")
    if net is not None:
        s.append(
            f"Over the month that is {net:+.0f} GWh per day of wind that was "
            f"{'planned but never arrived' if net > 0 else 'delivered beyond the plan'}."
        )
    if k.get("skill_vs_persistence") is not None:
        s.append(
            f"The forecast still beats 'assume the last known output' by "
            f"{k['skill_vs_persistence'] * 100:.0f}%, so use it, but correct it."
        )
    if k.get("adjusted_improvement") is not None and k.get("adjusted_mae") is not None:
        s.append(
            f"Subtracting the previous week's average miss (days D-8 to D-2, all settled by the "
            f"gate) cuts the typical miss from {gw(k['mae'])} to {gw(k['adjusted_mae'])} "
            f"({k['adjusted_improvement'] * 100:.0f}% better) with no look-ahead."
        )
    return s


@lru_cache(maxsize=4)
def timing(method: align.Method = "block") -> dict:
    """Value of waiting: January MAE and P90 for every half-hour gate on D-1."""
    rows = []
    for g in TIMING_GATES:
        month = january(g, 1, method, extras=False)
        st = metrics.error_stats(month["error_mw"])
        rows.append(
            {
                "gate": fmt_gate(g),
                "full_coverage": g >= EARLIEST_FULL_GATE,
                "hours_scored": st.get("n", 0),
                "coverage": _num(st.get("n", 0) / len(month)) if len(month) else None,
                "mae_mw": _num(st.get("mae")),
                "p90_abs_mw": _num(st.get("p90_abs")),
                "bias_mw": _num(st.get("bias")),
            }
        )
    by_gate = {r["gate"]: r for r in rows}
    ref = by_gate["09:20"]
    headline = None
    if ref["mae_mw"] and by_gate["15:30"]["mae_mw"] and by_gate["09:50"]["mae_mw"]:
        cut = 1 - by_gate["15:30"]["mae_mw"] / ref["mae_mw"]
        small = 1 - by_gate["09:50"]["mae_mw"] / ref["mae_mw"]
        headline = (
            f"Moving from the 09:20 to the 15:30 auction cuts the typical miss from "
            f"{ref['mae_mw']:,.0f} to {by_gate['15:30']['mae_mw']:,.0f} MW ({cut * 100:.0f}%); "
            f"waiting for N2EX at 09:50 buys only {small * 100:.0f}%. The bias barely moves, "
            f"so timing is not the fix."
        )
    run_times = sorted(
        data.load_manifest()["files"]["forecasts_wind.csv"]["publish_clock_times_utc"].items()
    )
    return {
        "alignment": method,
        "gates": rows,
        "presets": GATE_PRESETS,
        "run_publish_times_utc": [t for t, n in run_times if n > 5],
        "earliest_full_gate": fmt_gate(EARLIEST_FULL_GATE),
        "headline": headline,
    }


def _daily_mae(gate: time, method: align.Method) -> pd.Series:
    """Mean absolute error of each delivery day when the decision is taken at `gate`."""
    month = january(gate, 1, method, extras=False).dropna(subset=["error_mw"])
    return month.assign(abs_error=month["error_mw"].abs()).groupby("day")["abs_error"].mean()


def _run_gates() -> list[str]:
    """The usual WINDFOR publish times (HH:MM), read from the snapshot, never hard-coded."""
    clock = data.load_manifest()["files"]["forecasts_wind.csv"]["publish_clock_times_utc"]
    return sorted(t for t, n in clock.items() if n > 5)


@lru_cache(maxsize=4)
def waiting(method: align.Method = "block") -> dict:
    """How often does deciding later pay, day by day, and what would hindsight have chosen?

    Hindsight needs the actuals, so the best-run-per-day figures are an upper bound that no
    desk can reach in real time; they are shown to calibrate expectations, not as a strategy.
    """
    base_gate = timewin.DEFAULT_GATE
    base = _daily_mae(base_gate, method)

    comparisons = []
    for p in GATE_PRESETS:
        g = parse_gate(p["gate"])
        if g == base_gate:
            continue
        c = metrics.paired_gain(base, _daily_mae(g, method))
        comparisons.append(
            {
                "gate": p["gate"],
                "label": p["label"],
                "baseline_gate": fmt_gate(base_gate),
                "days": c["days"],
                "days_better": c["days_better"],
                "days_worse": c["days_worse"],
                "days_same": c["days_same"],
                "mean_gain_mw": _num(c["mean_gain"]),
                "median_gain_mw": _num(c["median_gain"]),
                "mean_gain_pct": _num(c["mean_gain_pct"]),
                "best_gain_mw": _num(c["best_gain"]),
                "best_gain_day": c["best_day"],
                "worst_gain_mw": _num(c["worst_gain"]),
                "worst_gain_day": c["worst_day"],
            }
        )

    run_gates = _run_gates()
    table = pd.DataFrame({t: _daily_mae(parse_gate(t), method) for t in run_gates})
    best, worst = table.idxmin(axis=1), table.idxmax(axis=1)
    runs = [
        {
            "run": t,
            "mean_mae_mw": _num(table[t].mean()),
            "best_days": int((best == t).sum()),
            "worst_days": int((worst == t).sum()),
        }
        for t in run_gates
    ]
    baseline_mae = float(base.mean())
    oracle_mae = float(table.min(axis=1).mean())
    latest = run_gates[-1]
    waited = comparisons[-1] if comparisons else None
    waited_mae = _daily_mae(parse_gate(waited["gate"]), method) if waited else None

    daily = pd.DataFrame(
        {
            "day": table.index,
            "mae_baseline_mw": base.reindex(table.index).values,
            "mae_waited_mw": waited_mae.reindex(table.index).values if waited else None,
            "best_run": best.values,
            "best_mae_mw": table.min(axis=1).values,
        }
    )
    daily["gain_mw"] = daily["mae_baseline_mw"] - daily["mae_waited_mw"]

    sentences = []
    if waited:
        sentences.append(
            f"Deciding at {waited['gate']} instead of {waited['baseline_gate']} gave a closer "
            f"forecast on {waited['days_better']} of {waited['days']} days and a worse one on "
            f"{waited['days_worse']}. The average gain is {waited['mean_gain_mw']:,.0f} MW "
            f"({waited['mean_gain_pct'] * 100:.0f}%), but half of the days gained less than "
            f"{waited['median_gain_mw']:,.0f} MW: a few large days carry the average."
        )
    latest_row = next(r for r in runs if r["run"] == latest)
    sentences.append(
        f"With hindsight, choosing the best run every day would have cut the typical miss by "
        f"{(1 - oracle_mae / baseline_mae) * 100:.0f}%, but that needs the actuals, so it is an "
        f"upper bound and not a strategy. Even the latest run ({latest}) was the closest on only "
        f"{latest_row['best_days']} of {len(table)} days, and the furthest on "
        f"{latest_row['worst_days']}."
    )
    return {
        "alignment": method,
        "baseline_gate": fmt_gate(base_gate),
        "days": int(len(table)),
        "baseline_mae_mw": _num(baseline_mae),
        "comparisons": comparisons,
        "runs": runs,
        "oracle_mae_mw": _num(oracle_mae),
        "oracle_improvement": _num(1 - oracle_mae / baseline_mae),
        "latest_run": latest,
        "daily": _records(daily),
        "sentences": sentences,
        "note": (
            "Hindsight only: the best run each day is known only once the actuals exist, so no "
            "desk can act on it. Each run time is treated as a decision taken the minute it is "
            "published."
        ),
    }


@lru_cache(maxsize=4)
def past_hours(method: align.Method = "block") -> dict:
    """Forecast rows that describe hours already over when the run was published.

    Every WINDFOR run is a fixed block that starts at 21:00 UTC the previous evening, so part
    of it is in the past. They are never selected by the rule and never scored as forecasts;
    this measures how close they are to the metered actual.
    """
    f = data.load_forecasts()
    lead = (f["start_time"] - f["publish_time"]).dt.total_seconds() / 3600
    past = f[lead < 0]
    per_run = past.groupby("publish_time").size()
    scored = past.merge(hourly_actuals(method), on="start_time", how="inner")
    scored["day"] = timewin.local_date(scored["start_time"])
    scored = scored[scored["day"].between(SCORED_FROM.isoformat(), SCORED_TO.isoformat())]
    err = scored["forecast_mw"] - scored["actual_mw"]
    return {
        "rows_total": int(len(f)),
        "rows_past": int(len(past)),
        "share_of_rows": _num(len(past) / len(f)),
        "hours_per_run_min": int(per_run.min()),
        "hours_per_run_max": int(per_run.max()),
        "scored_n": int(len(err)),
        "mae_mw": _num(err.abs().mean()),
        "bias_mw": _num(err.mean()),
    }


@lru_cache(maxsize=4)
def leadtime(method: align.Method = "block") -> dict:
    """Error against lead time over every (run, target) pair with a January target."""
    curve = metrics.lead_curve(pairs_frame(method))
    default = january(timewin.DEFAULT_GATE, 1, method)
    return {
        "alignment": method,
        "bucket_hours": metrics.LEAD_BUCKET_H,
        "buckets": _records(curve),
        "past_hours": past_hours(method),
        "decision_window_h": [_num(default["lead_h"].min()), _num(default["lead_h"].max())],
        "note": (
            "Buckets beyond 46.5 h hold fewer pairs and only early-morning runs, because every "
            "run covers a fixed 21:00-to-21:00 window."
        ),
    }


def meta() -> dict:
    m = data.load_manifest()
    return {
        "app": "day-ahead-wind-desk",
        "version": __version__,
        "scored_window": {
            "from": SCORED_FROM.isoformat(),
            "to": SCORED_TO.isoformat(),
            "days": len(SCORED_DAYS),
            "oos_split": OOS_SPLIT.isoformat(),
            "note": "Delivery days for purchase decisions made 1-31 January 2026.",
        },
        "warmup_from": WARMUP_FROM.isoformat(),
        "gate_presets": GATE_PRESETS,
        "default_gate": fmt_gate(timewin.DEFAULT_GATE),
        "earliest_full_gate": fmt_gate(EARLIEST_FULL_GATE),
        "alignment_methods": ["block", "point"],
        "snapshot": {
            "fetched_at_utc": m["fetched_at_utc"],
            "sources": m["sources"],
            "files": {
                name: {k: info[k] for k in ("sha256", "bytes", "rows") if k in info}
                for name, info in m["files"].items()
            },
            "runs": m["files"]["forecasts_wind.csv"]["runs"],
            "runs_per_utc_day": m["files"]["forecasts_wind.csv"]["runs_per_utc_day"],
            "publish_clock_times_utc": m["files"]["forecasts_wind.csv"]["publish_clock_times_utc"],
            "scored_half_hours": m["files"]["actuals_wind.csv"]["scored_half_hours"],
            "warnings": m["warnings"],
        },
    }
