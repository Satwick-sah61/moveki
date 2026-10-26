"""Fetch the January 2026 GB wind snapshot from Elexon BMRS and write it to data/.

Run by hand, once:  python scripts/fetch_elexon.py

It downloads two public datasets (no API key needed):
- WINDFOR: the wind generation forecast, one row per (publishTime, startTime), hourly targets.
- FUELHH: actual half-hourly generation by fuel type; we keep fuelType WIND.

Why a snapshot and not live calls: January 2026 is closed history, so the numbers never
change. Committing the CSVs makes every figure in the app deterministic, keeps the app up if
Elexon is down, and needs no database. The app never calls Elexon while serving requests.

Scope: purchase decisions made in January 2026, i.e. delivery days 2 January to 1 February.
Windows: WINDFOR by publishTime from 2025-12-21 to 2026-02-02 (runs published on 1 February are
never selectable by a January decision, but they give 1 February's hours every lead time for the
lead-time curve) and FUELHH by settlementDate from 2025-12-22 to 2026-02-01. December is
warm-up only (it gives the first days a persistence baseline and the trailing bias adjustment
its prior days) and is never scored or shown.

The script validates what the analysis relies on and writes data/manifest.json with the
source URLs, fetch time, row counts and SHA-256 hashes, so the snapshot can be reproduced
and checked.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
WINDFOR_URL = (
    f"{BASE}/WINDFOR/stream?publishDateTimeFrom=2025-12-21T00:00Z"
    "&publishDateTimeTo=2026-02-02T00:00Z"
)
FUELHH_URL = (
    f"{BASE}/FUELHH/stream?settlementDateFrom=2025-12-22&settlementDateTo=2026-02-01&fuelType=WIND"
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FORECASTS_CSV = DATA_DIR / "forecasts_wind.csv"
ACTUALS_CSV = DATA_DIR / "actuals_wind.csv"
MANIFEST = DATA_DIR / "manifest.json"

# Purchase decisions made in January 2026 deliver power on 2 January to 1 February.
SCORED_FROM = date(2026, 1, 2)
SCORED_TO = date(2026, 2, 1)  # inclusive


def parse_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def fmt_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_json(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as res:  # noqa: S310 (fixed https URL)
        payload = json.load(res)
    if not isinstance(payload, list):
        raise SystemExit(f"Unexpected payload shape from {url}: {type(payload).__name__}")
    return payload


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    # newline="" + lineterminator="\n" gives byte-identical files on Windows and Linux,
    # which keeps the SHA-256 in the manifest meaningful.
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def process_forecasts(raw: list[dict], warnings: list[str]) -> tuple[list[list], dict]:
    # Deduplicate on (publishTime, startTime), keeping the last occurrence.
    by_key: dict[tuple[datetime, datetime], float] = {}
    for r in raw:
        by_key[(parse_utc(r["publishTime"]), parse_utc(r["startTime"]))] = float(r["generation"])
    dupes = len(raw) - len(by_key)
    if dupes:
        warnings.append(f"WINDFOR: removed {dupes} duplicate (publishTime, startTime) rows")

    runs: dict[datetime, list[datetime]] = defaultdict(list)
    for pub, start in by_key:
        runs[pub].append(start)

    runs_per_day = Counter(pub.date() for pub in runs)
    odd_days = {str(d): n for d, n in sorted(runs_per_day.items()) if n != 8}
    if odd_days:
        warnings.append(f"WINDFOR: days with a run count other than 8: {odd_days}")

    windows = Counter()
    for pub, starts in runs.items():
        lo, hi = min(starts), max(starts)
        windows[
            (
                round((lo - pub).total_seconds() / 3600, 1),
                round((hi - pub).total_seconds() / 3600, 1),
                len(starts),
            )
        ] += 1

    rows = [
        [fmt_utc(pub), fmt_utc(start), f"{gen:g}"] for (pub, start), gen in sorted(by_key.items())
    ]
    summary = {
        "rows": len(rows),
        "runs": len(runs),
        "runs_per_utc_day": dict(Counter(runs_per_day.values())),
        "publish_clock_times_utc": dict(sorted(Counter(p.strftime("%H:%M") for p in runs).items())),
        "first_publish_utc": fmt_utc(min(runs)),
        "last_publish_utc": fmt_utc(max(runs)),
        "run_window_shapes_hours": [
            {"min_lead_h": lo, "max_lead_h": hi, "targets": n, "runs": c}
            for (lo, hi, n), c in sorted(windows.items())
        ],
        "generation_mw_min": min(by_key.values()),
        "generation_mw_max": max(by_key.values()),
    }
    return rows, summary


def process_actuals(raw: list[dict], warnings: list[str]) -> tuple[list[list], dict]:
    by_start: dict[datetime, dict] = {}
    for r in raw:
        if r.get("fuelType") != "WIND":
            continue
        by_start[parse_utc(r["startTime"])] = r
    dupes = sum(1 for r in raw if r.get("fuelType") == "WIND") - len(by_start)
    if dupes:
        warnings.append(f"FUELHH: removed {dupes} duplicate startTime rows")

    periods_per_day = Counter(r["settlementDate"] for r in by_start.values())
    odd_days = {d: n for d, n in sorted(periods_per_day.items()) if n != 48}
    if odd_days:
        warnings.append(f"FUELHH: days with a period count other than 48: {odd_days}")

    jan = [
        s
        for s in by_start
        if SCORED_FROM <= date.fromisoformat(by_start[s]["settlementDate"]) <= SCORED_TO
    ]
    expected_jan = ((SCORED_TO - SCORED_FROM).days + 1) * 48
    if len(jan) != expected_jan:
        warnings.append(f"FUELHH: scored window has {len(jan)} half-hours, expected {expected_jan}")

    lags = Counter()
    for s, r in by_start.items():
        lags[int((parse_utc(r["publishTime"]) - s).total_seconds() // 60)] += 1

    rows = [
        [
            fmt_utc(s),
            fmt_utc(parse_utc(r["publishTime"])),
            r["settlementDate"],
            int(r["settlementPeriod"]),
            f"{float(r['generation']):g}",
        ]
        for s, r in sorted(by_start.items())
    ]
    summary = {
        "rows": len(rows),
        "settlement_days": len(periods_per_day),
        "scored_half_hours": len(jan),
        "first_start_utc": fmt_utc(min(by_start)),
        "last_start_utc": fmt_utc(max(by_start)),
        "publish_lag_minutes_after_period_start": dict(sorted(lags.items())),
        "generation_mw_min": min(float(r["generation"]) for r in by_start.values()),
        "generation_mw_max": max(float(r["generation"]) for r in by_start.values()),
    }
    return rows, summary


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    fetched_at = datetime.now(UTC)
    warnings: list[str] = []

    print(f"GET {WINDFOR_URL}")
    windfor_raw = fetch_json(WINDFOR_URL)
    print(f"  {len(windfor_raw)} rows")
    print(f"GET {FUELHH_URL}")
    fuelhh_raw = fetch_json(FUELHH_URL)
    print(f"  {len(fuelhh_raw)} rows")

    forecast_rows, forecast_summary = process_forecasts(windfor_raw, warnings)
    actual_rows, actual_summary = process_actuals(fuelhh_raw, warnings)

    write_csv(FORECASTS_CSV, ["publish_time_utc", "start_time_utc", "generation_mw"], forecast_rows)
    write_csv(
        ACTUALS_CSV,
        [
            "start_time_utc",
            "publish_time_utc",
            "settlement_date",
            "settlement_period",
            "generation_mw",
        ],
        actual_rows,
    )

    manifest = {
        "description": (
            "GB wind forecasts (WINDFOR) and actual wind generation (FUELHH, fuelType WIND) "
            "from Elexon BMRS, snapshot for the Day-Ahead Wind Desk."
        ),
        "fetched_at_utc": fmt_utc(fetched_at),
        "scored_window": {
            "from": SCORED_FROM.isoformat(),
            "to": SCORED_TO.isoformat(),
            "note": (
                "Delivery days for purchase decisions made in January 2026; "
                "earlier rows are warm-up only."
            ),
        },
        "sources": {
            "WINDFOR": {"url": WINDFOR_URL, "raw_rows": len(windfor_raw)},
            "FUELHH": {"url": FUELHH_URL, "raw_rows": len(fuelhh_raw)},
        },
        "files": {
            FORECASTS_CSV.name: {
                "sha256": sha256_of(FORECASTS_CSV),
                "bytes": FORECASTS_CSV.stat().st_size,
                **forecast_summary,
            },
            ACTUALS_CSV.name: {
                "sha256": sha256_of(ACTUALS_CSV),
                "bytes": ACTUALS_CSV.stat().st_size,
                **actual_summary,
            },
        },
        "warnings": warnings,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({k: v for k, v in manifest.items() if k != "sources"}, indent=2))
    if warnings:
        print(f"\n{len(warnings)} warning(s) recorded in the manifest.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
