"""Align half-hourly actuals (FUELHH) to the hourly forecast targets (WINDFOR).

FUELHH generation is the average MW over a 30-minute settlement period. The default actual for
forecast hour t is the "block" mean of the two periods starting at t and t+30 min, i.e. the
average MW over [t, t+1h). That matches the hourly blocks traded in the GB day-ahead auctions
and keeps energy (MWh) consistent. "point" takes the period starting at t instead, which is
offered as a sensitivity check. If a half-hour is missing the hour is dropped, never guessed.
"""

from typing import Literal

import pandas as pd

Method = Literal["block", "point"]


def hourly_actuals(actuals: pd.DataFrame, method: Method = "block") -> pd.DataFrame:
    """Return one row per complete hour: start_time (UTC, on the hour) and actual_mw."""
    df = actuals[["start_time", "actual_mw"]].copy()
    df["hour"] = df["start_time"].dt.floor("1h")
    df["minute"] = df["start_time"].dt.minute

    if method == "block":
        # Complete means exactly the :00 and :30 periods are present (a duplicated :00 with a
        # missing :30 is not an hour).
        grouped = df.groupby("hour").agg(
            mean=("actual_mw", "mean"), count=("actual_mw", "size"), minutes=("minute", "nunique")
        )
        complete = grouped[(grouped["count"] == 2) & (grouped["minutes"] == 2)]
        out = complete["mean"].rename("actual_mw").reset_index()
    elif method == "point":
        on_the_hour = df[df["minute"] == 0]
        out = on_the_hour[["hour", "actual_mw"]].reset_index(drop=True)
    else:
        raise ValueError(f"unknown alignment method: {method!r}")

    return out.rename(columns={"hour": "start_time"}).sort_values("start_time", ignore_index=True)
