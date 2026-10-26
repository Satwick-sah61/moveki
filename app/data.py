"""Load the committed Elexon snapshot into pandas, once per process.

Everything downstream works in UTC. Timestamps are parsed as tz-aware UTC with one fixed
resolution so that merge_asof and joins never fail on a dtype mismatch.
"""

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

# Built from __file__ because the working directory is not the repo root on Vercel.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

UTC_NS = "datetime64[ns, UTC]"


def to_utc(values) -> pd.Series:
    """Parse ISO strings (or datetimes) into tz-aware UTC timestamps at ns resolution."""
    return pd.to_datetime(values, utc=True).astype(UTC_NS)


@lru_cache(maxsize=1)
def load_forecasts() -> pd.DataFrame:
    """WINDFOR rows: publish_time, start_time, forecast_mw. Sorted by publish_time, start_time."""
    df = pd.read_csv(DATA_DIR / "forecasts_wind.csv")
    out = pd.DataFrame(
        {
            "publish_time": to_utc(df["publish_time_utc"]),
            "start_time": to_utc(df["start_time_utc"]),
            "forecast_mw": df["generation_mw"].astype("float64"),
        }
    )
    return out.sort_values(["publish_time", "start_time"], ignore_index=True)


@lru_cache(maxsize=1)
def load_actuals() -> pd.DataFrame:
    """FUELHH WIND rows: start_time, publish_time, settlement_date, settlement_period, actual_mw."""
    df = pd.read_csv(DATA_DIR / "actuals_wind.csv")
    out = pd.DataFrame(
        {
            "start_time": to_utc(df["start_time_utc"]),
            "publish_time": to_utc(df["publish_time_utc"]),
            "settlement_date": df["settlement_date"].astype(str),
            "settlement_period": df["settlement_period"].astype("int64"),
            "actual_mw": df["generation_mw"].astype("float64"),
        }
    )
    return out.sort_values("start_time", ignore_index=True)


@lru_cache(maxsize=1)
def load_manifest() -> dict:
    return json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
