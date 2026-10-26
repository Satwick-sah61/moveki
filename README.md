# Day-Ahead Wind Desk

A web app for a UK electricity buying desk. It shows the latest GB wind forecast that was
**available at day-ahead gate closure** and scores that forecast against **actual wind output**,
for every purchase decision made in January 2026, using Elexon BMRS data only
(WINDFOR forecasts, FUELHH WIND actuals).

**Live app:** https://moveki.vercel.app · **API docs:** https://moveki.vercel.app/api/docs

[![CI](https://github.com/Satwick-sah61/moveki/actions/workflows/ci.yml/badge.svg)](https://github.com/Satwick-sah61/moveki/actions/workflows/ci.yml)

## What it answers

1. **What forecast did the desk actually have when it had to decide?** For each hour of
   delivery day D, the app takes the newest WINDFOR run published *at or before* the gate
   (default 09:20 UK on D-1, the EPEX 60-minute day-ahead auction; N2EX 09:50 and the 15:30
   half-hourly auction are presets, any time is allowed). It never uses a later run.
2. **How wrong was it, in numbers a buyer can act on?** Typical miss (MAE), bias with its
   direction, "9 hours in 10 the miss stayed under X", an 80% band on every hour, skill against a
   no-forecast baseline, and plain-language buying guidance generated from the numbers.

Three screens: **Decision replay** (one day, with a *Reveal* toggle for what actually
happened), **Scorecard** (all 31 decision days) and **Timing** (is it worth deciding later, how
often waiting actually pays day by day, and error against lead time), plus a **Method & data**
drawer.

## Findings (09:20 gate, decisions 1–31 January 2026, 744 hours)

| | Value |
|---|---|
| Typical miss (MAE) | **2,039 MW** (RMSE 2,505 MW, WAPE 18.1%) |
| Bias (forecast − actual) | **+1,748 MW**, forecast high in **85%** of hours |
| 9 hours in 10 the miss was under | **4,098 MW** (P95 5,283 MW, max 6,870 MW) |
| Planned wind that never arrived | **+42 GWh per day** on average; worst day 28 Jan, +129 GWh |
| vs persistence ("last known output") | persistence MAE 4,111 MW → the forecast is **50% better** |
| Last week's bias removed (no look-ahead) | MAE **1,615 MW (−21%)**, bias +257 MW |
| 80% band hit rate, out of sample | **88%** (calibrated 2–16 Jan, tested 17 Jan–1 Feb) |
| Value of waiting | On average 09:50 is −1% and 15:30 is −8% (MAE 1,873 MW), but 15:30 beat 09:20 on only **16 of 31 days** (the median day gains 35 MW); the best run each day in hindsight would give −24%, an upper bound nobody can act on |

The bias is the headline. It is still about +1.4 GW for forecasts made only 0–3 hours ahead,
when the weather is essentially known, and even the 21% of forecast rows that describe hours
already over (never used as forecasts) read +1.67 GW above the meter, so most of it is not
forecasting skill: WINDFOR is a
forecast of what the wind fleet could produce, FUELHH is metered output after balancing actions
such as curtailment. The app states this as a hypothesis (proving it needs curtailment volumes,
which is pilot work) and gives the desk something to do about it today: the bias-adjusted line.
`python scripts/analysis.py` reproduces every number above from the same code the API runs.

## Repository layout

```
app/                 Python backend (FastAPI)
  main.py            the app: six /api routes, then the React build served at /
  schemas.py         Pydantic response models (= the API contract, see /api/docs)
  desk.py            service layer: replay, scorecard, timing, lead-time, meta (cached)
  gate.py            the decision rule: newest run at or before the gate (pandas.merge_asof)
  timewin.py         UK delivery days and gate times -> UTC (Europe/London only here)
  align.py           half-hourly actuals -> hourly block mean (or point match)
  metrics.py         MAE/RMSE/bias/WAPE/quantiles, bands, persistence skill, bias adjustment, flags
  data.py            loads the snapshot once per process (tz-aware UTC)
data/                committed Elexon snapshot: forecasts_wind.csv, actuals_wind.csv, manifest.json
scripts/
  fetch_elexon.py    downloads and validates the snapshot, writes the manifest (run by hand)
  analysis.py        prints the headline numbers quoted above
tests/               pytest: rule, time zones, alignment, metrics, snapshot integrity, API contract
frontend/            React 19 + TypeScript + Vite + Recharts
  src/views/         Replay.tsx, Scorecard.tsx, Timing.tsx
  src/charts/        ReplayChart, CalendarHeatmap, HourOfDayChart, HistogramChart, TimingChart, LeadTimeChart
  src/components/    Controls, MethodDrawer, Tile, Switch
  src/lib/           format.ts (UK time), urlState.ts (view state in the URL), useFetch.ts
  src/api.ts         typed client; src/types.ts mirrors app/schemas.py
docs/decisions.md    the design decisions, one paragraph each, and what was deliberately not built
Dockerfile           multi-stage: Node builds the page, python:3.13-slim serves it (non-root, HEALTHCHECK)
docker-compose.yml   docker compose up --build -> http://localhost:8000
vercel.json          build command for the React bundle; keeps node_modules/tests out of the function
.github/workflows/   CI: ruff, pytest, tsc + vite build, docker build + health smoke test
```

## How to start

**Docker (one command, same image as production would use):**

```bash
docker compose up --build
```

Then open http://localhost:8000 (API docs at http://localhost:8000/api/docs).

**Development (two terminals, hot reload):**

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt     # macOS/Linux: .venv/bin/pip
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm ci && npm run dev                  # http://localhost:5173, /api proxied to :8000
```

**Tests and checks:**

```bash
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
.venv/Scripts/pytest                                  # 67 tests, ~10 s
cd frontend && npm run build                          # tsc -b + vite build
```

**Refresh the data snapshot** (not needed to run the app; the result is committed):

```bash
.venv/Scripts/python scripts/fetch_elexon.py
```

## Method in brief

- **Scope.** The brief limits the data to purchase decisions made in January 2026. A day-ahead
  decision on D-1 buys power for D, so the app scores delivery days 2 January to 1 February
  (31 days). December rows are warm-up only (persistence baseline, bias adjustment).
- **Rule.** `forecast(t)` = the WINDFOR row for hour t with the greatest `publishTime <= gate`,
  inclusive, selected per hour. Hours with no eligible run are gaps, shown and counted, never
  filled. One `merge_asof` call; a no-look-ahead test checks every day at five gates.
- **Alignment.** FUELHH is half-hourly, WINDFOR hourly. Hour t's actual is the mean of the two
  half-hours in [t, t+1h); matching the first half-hour instead changes the MAE by ~17 MW
  (`align=point`).
- **Time.** Everything is UTC except three edges (delivery day, gate, display), which use
  Europe/London. Tests cover a BST date and both 2026 clock changes.
- **Error** = forecast − actual; positive means the forecast read high and the buyer was short.
- **Band.** P10–P90 of the signed error of all (run, hour) pairs at the same lead (3 h buckets),
  leaving the shown day out; hit rate verified out of sample.
- **Persistence.** The last FUELHH half-hour *published* by the gate, held flat.
- **Bias adjustment.** Subtract the mean error of delivery days D-8..D-2 at the same gate
  (all settled by D-1). A correction of Elexon's forecast, not a forecast of our own.
- **Unusual hours/days.** |error| in the top 5%; daily net error beyond 2σ. Flags, not a model.

Details and the reasoning behind each choice: [docs/decisions.md](docs/decisions.md).

## Data

Elexon BMRS, public, no key: `WINDFOR` (publishTime 2025-12-21 to 2026-02-02, 344 runs, 8 per
day, 73 hourly targets each) and `FUELHH` with fuelType WIND (settlement dates 2025-12-22 to
2026-02-01, 2,016 half-hours). Fetched 2026-10-25 23:36 UTC; SHA-256 of each CSV in `data/manifest.json`
and checked by a test. The app never calls Elexon while serving.

## Limitations

- One winter month: errors are autocorrelated and the sample is small, so every KPI shows its n
  and no claim is made beyond the window. A longer pilot is the obvious next step.
- The bias explanation (scope/curtailment mismatch) is a hypothesis; the two datasets in scope
  cannot prove it.
- WINDFOR's interface spec labels the value "Forecast Peak Wind Generation"; whether it is an
  hourly average or a point value is not stated, hence the measured alignment sensitivity.
- Auction gate times are presets (EPEX 09:20 / N2EX 09:50 / EPEX 15:30 UK) and configurable.

## Deployment

Vercel Hobby, zero-config FastAPI (`app/main.py`) plus a `buildCommand` for the React bundle;
the same code runs in the Docker image. See decision 13 in `docs/decisions.md` for the fallbacks.

## AI tools used

Claude Code was used as a pair programmer for planning, scaffolding, test ideas and code review.
