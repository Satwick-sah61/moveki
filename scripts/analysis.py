"""Print the headline numbers the README and the video quote, from the same code the API uses.

Run:  python scripts/analysis.py            (from the repo root, with the venv active)

Everything here reuses app.desk, so a figure in the README can be reproduced by anyone with
one command and cannot drift from what the app shows.
"""

from __future__ import annotations

import sys
from datetime import date, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import desk, metrics  # noqa: E402


def mw(x: float | None) -> str:
    return "-" if x is None else f"{x:,.0f} MW"


def pct(x: float | None) -> str:
    return "-" if x is None else f"{x * 100:.0f}%"


def main() -> None:
    gate = time(9, 20)
    sc = desk.scorecard(gate)
    k = sc["kpis"]
    print(
        f"Window: delivery {desk.SCORED_FROM} to {desk.SCORED_TO} ({len(desk.SCORED_DAYS)} days), "
        f"decisions made 1-31 January 2026; gate {sc['gate']} UK on D-1; "
        f"alignment {sc['alignment']}.\n"
    )

    print("HEADLINE (09:20 gate, all hours)")
    rows = [
        ("Hours scored", f"{k['n']} of {k['hours_expected']} ({pct(k['coverage'])})"),
        ("MAE (typical miss)", mw(k["mae"])),
        ("RMSE", mw(k["rmse"])),
        (
            "Bias (forecast - actual)",
            f"{k['bias']:+,.0f} MW, high in {pct(k['share_over'])} of hours",
        ),
        ("WAPE", f"{k['wape'] * 100:.1f}%"),
        (
            "P50 / P90 / P95 |error|",
            f"{mw(k['p50_abs'])} / {mw(k['p90_abs'])} / {mw(k['p95_abs'])}",
        ),
        ("Max |error|", f"{mw(k['max_abs'])} at {k['max_abs_at']}"),
        ("P90 shortfall headroom", mw(k["p90_shortfall"])),
        (
            "Persistence MAE / skill",
            f"{mw(k['persistence_mae'])} / {pct(k['skill_vs_persistence'])}",
        ),
        (
            "Bias-adjusted MAE / bias",
            f"{mw(k['adjusted_mae'])} / {k['adjusted_bias']:+,.0f} MW "
            f"({pct(k['adjusted_improvement'])} better)",
        ),
        ("80% band coverage (out of sample)", pct(k["band_coverage_oos"])),
        ("Mean daily net energy error", f"{k['mean_daily_net_gwh']:+.1f} GWh/day"),
        ("Alignment sensitivity (point MAE)", mw(k["alignment_other_mae"])),
        (
            "Unusual hours / days",
            f"{k['unusual_hours']} (|error| >= {mw(k['unusual_hour_threshold_mw'])}) / "
            f"{k['unusual_days']}",
        ),
    ]
    for label, value in rows:
        print(f"  {label:<36} {value}")

    print("\nWORST DAYS (net energy error, GWh)")
    for d in sc["worst_days"]:
        flag = "   unusual" if d["unusual"] else ""
        print(f"  {d['day']}  {d['net_gwh']:+7.1f} GWh   MAE {mw(d['mae_mw'])}{flag}")

    print("\nBUYING SENTENCES")
    for s in sc["sentences"]:
        print(f"  - {s}")

    print("\nTIMING (value of waiting, D-1 gates)")
    tm = desk.timing()
    by_gate = {g["gate"]: g for g in tm["gates"]}
    for g in ("02:00", "02:30", "09:20", "09:50", "15:30", "23:30"):
        r = by_gate[g]
        print(
            f"  {g}  MAE {mw(r['mae_mw'])}  P90 {mw(r['p90_abs_mw'])}  "
            f"bias {r['bias_mw']:+,.0f} MW  coverage {pct(r['coverage'])}"
        )
    print(f"  {tm['headline']}")

    print("\nERROR BY LEAD TIME (3 h buckets, all (run, hour) pairs)")
    for b in desk.leadtime()["buckets"]:
        print(
            f"  {b['bucket']:>2}-{b['bucket'] + metrics.LEAD_BUCKET_H:<2} h  n={b['n']:<4} "
            f"MAE {mw(b['mae_mw'])}  bias {b['bias_mw']:+,.0f} MW"
        )

    print("\nDEMO DAY (28 Jan, 09:20)")
    rp = desk.replay(date(2026, 1, 28), gate)
    run = rp["runs_used"][0]
    print(
        f"  run used: published {run['publish_time']}, {run['age_h']:.1f} h before the gate, "
        f"lead {run['lead_min']}-{run['lead_max']} h"
    )
    b, a = rp["before_reveal"], rp["after_reveal"]
    print(
        f"  forecast energy {b['forecast_energy_gwh']} GWh (band {b['band_energy_lo_gwh']}-"
        f"{b['band_energy_hi_gwh']}), actual {a['actual_energy_gwh']} GWh, "
        f"net {a['net_gwh']:+} GWh, day MAE {mw(a['mae_mw'])}, "
        f"adjusted MAE {mw(a['adjusted_mae_mw'])}, unusual day: {a['unusual_day']}"
    )


if __name__ == "__main__":
    main()
