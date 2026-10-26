"""UK delivery days and gate times, converted to UTC.

Europe/London is used only here, at the edges. Everything else works in UTC, so the code
behaves the same on a clock-change day as on any other day. In January GMT equals UTC, which
would hide a timezone bug; the tests therefore also cover a BST date and both clock changes.
"""

from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import pandas as pd

from app.data import UTC_NS

LONDON = ZoneInfo("Europe/London")

DEFAULT_GATE = time(9, 20)  # EPEX GB day-ahead 60-minute auction, the earliest GB gate


def gate_utc(delivery_day: date, gate: time = DEFAULT_GATE, days_before: int = 1) -> pd.Timestamp:
    """The decision cutoff: `gate` UK local time on the day `days_before` the delivery day."""
    local = datetime.combine(delivery_day - timedelta(days=days_before), gate, tzinfo=LONDON)
    utc = local.astimezone(UTC)
    # On the spring clock change 01:00-01:59 UK does not exist; refuse it rather than map it to
    # an instant the user did not type. An ambiguous autumn time takes its first occurrence.
    if utc.astimezone(LONDON).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError(f"{gate:%H:%M} UK does not exist on {local:%Y-%m-%d} (clock change)")
    # as_unit("ns") keeps every timestamp in the app at one resolution (see data.UTC_NS).
    return pd.Timestamp(utc).as_unit("ns")


@lru_cache(maxsize=512)
def delivery_hours_utc(delivery_day: date) -> pd.Series:
    """Hourly start times (UTC) of the UK local calendar day: 24, or 23/25 on clock changes."""
    start = datetime.combine(delivery_day, time(0), tzinfo=LONDON).astimezone(UTC)
    end = datetime.combine(delivery_day + timedelta(days=1), time(0), tzinfo=LONDON).astimezone(UTC)
    hours = pd.date_range(start, end, freq="1h", inclusive="left")
    return pd.Series(hours, name="start_time").astype(UTC_NS)


def local_date(ts: pd.Series) -> pd.Series:
    """UK calendar date (ISO string) of each UTC timestamp; equals FUELHH settlementDate."""
    return ts.dt.tz_convert(LONDON).dt.strftime("%Y-%m-%d")


def format_london(ts: pd.Timestamp | datetime, fmt: str = "%d %b %H:%M") -> str:
    """Display helper: UK local time with the convention used across the app."""
    return pd.Timestamp(ts).tz_convert(LONDON).strftime(fmt)
