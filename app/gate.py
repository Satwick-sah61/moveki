"""The decision rule: which forecast could the desk see at gate closure?

For each target hour, take the forecast row with the greatest publish_time at or before the
cutoff. A run published exactly at the cutoff counts (inclusive). Never use a later run. If no
eligible row exists the hour stays empty; it is counted as a gap, never filled.

The whole rule is one pandas.merge_asof call: for every target (sorted by cutoff) find the last
forecast row (sorted by publish_time) with publish_time <= cutoff and the same start_time.
"""

import numpy as np
import pandas as pd

from app.data import to_utc


def latest_at_cutoff(forecasts: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Select, per target hour, the newest forecast published at or before its cutoff.

    forecasts: publish_time, start_time, forecast_mw (UTC).
    targets:   start_time, cutoff (UTC); any other columns are carried through.

    Returns targets plus publish_time, forecast_mw (NaN/NaT when nothing was available),
    lead_h (start_time - publish_time) and age_h (cutoff - publish_time), sorted by start_time.
    """
    right = forecasts[["publish_time", "start_time", "forecast_mw"]].copy()
    left = targets.copy()
    # merge_asof insists on identical key dtypes; a scalar Timestamp broadcast into a column
    # comes out at microsecond resolution in pandas 3, so normalise every key to ns first.
    for frame, cols in ((left, ("cutoff", "start_time")), (right, ("publish_time", "start_time"))):
        for col in cols:
            frame[col] = to_utc(frame[col])
    # A row with no publish time was never available; a duplicated key keeps its last value
    # (the snapshot has neither, but the rule should not depend on that).
    right = right.dropna(subset=["publish_time"]).drop_duplicates(
        ["publish_time", "start_time"], keep="last"
    )
    right = right.sort_values("publish_time", kind="stable")
    left = left.sort_values("cutoff", kind="stable")
    out = pd.merge_asof(
        left,
        right,
        left_on="cutoff",
        right_on="publish_time",
        by="start_time",
        direction="backward",
        allow_exact_matches=True,
    )
    out["lead_h"] = (out["start_time"] - out["publish_time"]).dt.total_seconds() / 3600
    out["age_h"] = (out["cutoff"] - out["publish_time"]).dt.total_seconds() / 3600
    return out.sort_values("start_time", ignore_index=True)


def latest_actual_at_cutoff(actuals: pd.DataFrame, cutoff: pd.Timestamp) -> float | None:
    """The last actual half-hour that had been *published* by the cutoff (persistence baseline).

    FUELHH publish_time is normally the end of the period (+30 min), occasionally later, so
    the availability rule is applied to publish_time, not start_time.
    """
    value = latest_actuals_at_cutoffs(actuals, pd.Series([cutoff])).iloc[0]
    return None if pd.isna(value) else float(value)


def latest_actuals_at_cutoffs(actuals: pd.DataFrame, cutoffs: pd.Series) -> pd.Series:
    """Vectorised form of latest_actual_at_cutoff for many cutoffs (one per delivery day).

    Rows are ordered by publish_time; a running "latest start_time so far" index turns the
    question into one searchsorted per cutoff.
    """
    a = actuals.sort_values("publish_time", kind="stable")
    publish = a["publish_time"].to_numpy()
    start = a["start_time"].to_numpy()
    mw = a["actual_mw"].to_numpy()
    latest_idx = np.empty(len(a), dtype="int64")
    best = 0
    for i in range(len(a)):
        if start[i] >= start[best]:
            best = i
        latest_idx[i] = best
    pos = np.searchsorted(publish, to_utc(cutoffs).to_numpy(), side="right") - 1
    values = np.where(pos >= 0, mw[latest_idx[np.clip(pos, 0, None)]], np.nan)
    return pd.Series(values, index=cutoffs.index, dtype="float64")


def runs_covering(forecasts: pd.DataFrame, hours: pd.Series) -> pd.DataFrame:
    """All forecast rows whose start_time is one of `hours`, for drawing the fan of runs."""
    return forecasts[forecasts["start_time"].isin(hours)].sort_values(
        ["publish_time", "start_time"], ignore_index=True
    )
