"""Accuracy metrics. Pure functions over pandas objects: no HTTP, no file I/O.

Sign convention everywhere: error = forecast - actual. Positive means the forecast read high,
so less wind arrived than planned and a buyer who trusted it is short.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

LEAD_BUCKET_H = 3


def _clean(x) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def error_stats(err: pd.Series) -> dict:
    """Headline statistics of a signed-error series (MW)."""
    e = err.dropna()
    n = int(len(e))
    if n == 0:
        return {"n": 0}
    ae = e.abs()
    return {
        "n": n,
        "mae": float(ae.mean()),
        "rmse": float(np.sqrt((e**2).mean())),
        "bias": float(e.mean()),
        "share_over": float((e > 0).mean()),
        "p50_abs": float(ae.quantile(0.5)),
        "p90_abs": float(ae.quantile(0.9)),
        "p95_abs": float(ae.quantile(0.95)),
        "max_abs": float(ae.max()),
        # 90th percentile of the signed error: plan this much less wind than forecast to be
        # covered 9 hours in 10.
        "p90_shortfall": float(e.quantile(0.9)),
    }


def wape(forecast: pd.Series, actual: pd.Series) -> float | None:
    """Weighted absolute percentage error: sum |error| / sum actual. MAPE is avoided because it
    explodes in low-wind hours."""
    mask = forecast.notna() & actual.notna()
    denom = float(actual[mask].sum())
    if denom == 0:
        return None
    return float((forecast[mask] - actual[mask]).abs().sum() / denom)


def skill(mae_forecast: float | None, mae_baseline: float | None) -> float | None:
    """1 - MAE_forecast / MAE_baseline. 0 = no better than the baseline, 1 = perfect."""
    if mae_forecast is None or not mae_baseline:
        return None
    return float(1 - mae_forecast / mae_baseline)


def daily_summary(scored: pd.DataFrame) -> pd.DataFrame:
    """Per delivery day: hours scored, MAE, bias, net energy error (GWh, hourly MW summed)."""
    df = scored.dropna(subset=["error_mw"])
    g = df.groupby("day")["error_mw"]
    out = pd.DataFrame(
        {
            "hours": g.size(),
            "mae_mw": g.apply(lambda s: s.abs().mean()),
            "bias_mw": g.mean(),
            "net_gwh": g.sum() / 1000.0,
        }
    )
    return out.reset_index().sort_values("day", ignore_index=True)


def flag_unusual(
    scored: pd.DataFrame, daily: pd.DataFrame, hour_q: float = 0.95
) -> tuple[pd.Series, pd.Series]:
    """Transparent anomaly flags, no model.

    Hour: |error| at or above the month's 95th percentile. Day: net energy error more than two
    standard deviations from the month's mean. Both are rules a trader can check by hand.
    """
    abs_err = scored["error_mw"].abs()
    hour_threshold = abs_err.quantile(hour_q)
    unusual_hours = abs_err >= hour_threshold
    mu, sd = daily["net_gwh"].mean(), daily["net_gwh"].std(ddof=0)
    unusual_days = (
        (daily["net_gwh"] - mu).abs() > 2 * sd if sd > 0 else pd.Series(False, index=daily.index)
    )
    return unusual_hours.fillna(False), unusual_days


def by_hour_of_day(scored: pd.DataFrame) -> pd.DataFrame:
    """Bias and MAE for each UK local hour of the delivery day (n is small: one per day)."""
    df = scored.dropna(subset=["error_mw"]).copy()
    df["hour"] = df["local_hour"]
    g = df.groupby("hour")["error_mw"]
    out = pd.DataFrame(
        {"n": g.size(), "bias_mw": g.mean(), "mae_mw": g.apply(lambda s: s.abs().mean())}
    )
    return out.reset_index().sort_values("hour", ignore_index=True)


def histogram(err: pd.Series, width_mw: float = 500.0) -> list[dict]:
    """Signed-error histogram in fixed-width bins (MW)."""
    e = err.dropna()
    if e.empty:
        return []
    lo = math.floor(e.min() / width_mw) * width_mw
    hi = math.ceil(e.max() / width_mw) * width_mw
    edges = np.arange(lo, hi + width_mw, width_mw)
    counts, _ = np.histogram(e, bins=edges)
    return [
        {"lo": float(a), "hi": float(b), "n": int(n)}
        for a, b, n in zip(edges[:-1], edges[1:], counts, strict=True)
    ]


def lead_bucket(lead_h: pd.Series, width: int = LEAD_BUCKET_H) -> pd.Series:
    return (np.floor(lead_h / width) * width).astype("int64")


def lead_curve(pairs: pd.DataFrame, width: int = LEAD_BUCKET_H) -> pd.DataFrame:
    """Error by lead-time bucket over all (run, target) pairs: n, MAE, bias, P10/P90 error."""
    df = pairs.dropna(subset=["error_mw"]).copy()
    df["bucket"] = lead_bucket(df["lead_h"], width)
    g = df.groupby("bucket")["error_mw"]
    out = pd.DataFrame(
        {
            "n": g.size(),
            "mae_mw": g.apply(lambda s: s.abs().mean()),
            "bias_mw": g.mean(),
            "p10_err": g.quantile(0.10),
            "p90_err": g.quantile(0.90),
        }
    )
    return out.reset_index().sort_values("bucket", ignore_index=True)


def error_quantiles_by_bucket(
    pairs: pd.DataFrame, width: int = LEAD_BUCKET_H, exclude_day: str | None = None
) -> pd.DataFrame:
    """Signed-error P10/P90 per lead bucket, optionally leaving one delivery day out."""
    df = pairs.dropna(subset=["error_mw"])
    if exclude_day is not None:
        df = df[df["day"] != exclude_day]
    df = df.assign(bucket=lead_bucket(df["lead_h"], width))
    g = df.groupby("bucket")["error_mw"]
    return pd.DataFrame({"n": g.size(), "p10_err": g.quantile(0.10), "p90_err": g.quantile(0.90)})


def apply_band(
    selected: pd.DataFrame, quantiles: pd.DataFrame, width: int = LEAD_BUCKET_H
) -> pd.DataFrame:
    """Attach an empirical band for the *actual* to each selected hour.

    error = forecast - actual, so actual = forecast - error: the band for the actual is
    [forecast - P90(error), forecast - P10(error)]. With a positive bias it sits below the line.
    """
    out = selected.copy()
    b = lead_bucket(out["lead_h"].fillna(-1), width)
    q = quantiles.reindex(b.values)
    out["band_lo_mw"] = out["forecast_mw"].values - q["p90_err"].values
    out["band_hi_mw"] = out["forecast_mw"].values - q["p10_err"].values
    out["band_n"] = q["n"].fillna(0).astype("int64").values
    return out


def band_coverage(selected: pd.DataFrame) -> float | None:
    """Share of hours whose actual fell inside [band_lo, band_hi]."""
    df = selected.dropna(subset=["actual_mw", "band_lo_mw", "band_hi_mw"])
    if df.empty:
        return None
    inside = (df["actual_mw"] >= df["band_lo_mw"]) & (df["actual_mw"] <= df["band_hi_mw"])
    return float(inside.mean())


def trailing_bias(
    scored: pd.DataFrame, days_back_from: int = 8, days_back_to: int = 2, min_hours: int = 72
) -> pd.Series:
    """Per delivery day, the mean error of the same gate over days D-8..D-2 (fully settled by the
    gate on D-1), or NaN when fewer than `min_hours` scored hours exist. No leakage: D-1 is
    excluded because its actuals are not all published by 09:20 on D-1.
    """
    daily = scored.dropna(subset=["error_mw"]).groupby("day")["error_mw"].agg(["sum", "size"])
    daily.index = pd.to_datetime(daily.index)
    days = pd.to_datetime(pd.Series(scored["day"].unique()))
    # A full calendar from the earliest window start, so a rolling window of
    # (days_back_from - days_back_to + 1) days ending at D - days_back_to is a plain shift.
    calendar = pd.date_range(days.min() - pd.Timedelta(days=days_back_from), days.max(), freq="D")
    full = daily.reindex(calendar).fillna(0.0)
    width = days_back_from - days_back_to + 1
    window = full.rolling(width, min_periods=1).sum().shift(days_back_to)
    hours = window["size"].fillna(0.0)
    mean = (window["sum"] / hours.where(hours > 0)).where(hours >= min_hours)
    lookup = pd.Series(mean.to_numpy(), index=calendar.strftime("%Y-%m-%d"))
    return scored["day"].map(lookup).astype("float64")


def paired_gain(base: pd.Series, other: pd.Series, tol: float = 1e-9) -> dict:
    """Compare two per-day error series day by day (e.g. daily MAE at two decision times).

    gain = base - other, so a positive gain means `other` was closer to the actual that day.
    Only days present in both series are compared.
    """
    both = pd.concat({"base": base, "other": other}, axis=1).dropna()
    gain = both["base"] - both["other"]
    if gain.empty:
        return {"days": 0}
    return {
        "days": int(len(gain)),
        "days_better": int((gain > tol).sum()),
        "days_worse": int((gain < -tol).sum()),
        "days_same": int((gain.abs() <= tol).sum()),
        "mean_gain": float(gain.mean()),
        "median_gain": float(gain.median()),
        "mean_gain_pct": float(gain.mean() / both["base"].mean()),
        "best_gain": float(gain.max()),
        "best_day": str(gain.idxmax()),
        "worst_gain": float(gain.min()),
        "worst_day": str(gain.idxmin()),
    }
