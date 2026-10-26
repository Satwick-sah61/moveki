# Design decisions

Short records of the choices that shape the app, written so a reviewer can follow the
reasoning without reading the code first. Each is one paragraph; together they double as the
speaker notes for the technical walkthrough.

## 1. One FastAPI app serves both the API and the React build

The API lives under `/api` and the built front end (Vite) is served from the same app at `/`.
The same `app` object runs under uvicorn in development, inside one Docker image and as a
Vercel Python function, so there is one code path to test and no CORS, no environment-specific
URLs and no second service to keep alive. In development Vite runs on its own port and proxies
`/api` to uvicorn, so the browser still sees one origin. FastAPI's `app.frontend()` gives API
routes priority over static files whatever the declaration order.

## 2. Committed data snapshot instead of live Elexon calls

January 2026 is closed history: WINDFOR runs never change once published and FUELHH for the
window is settled. A committed snapshot with SHA-256 hashes in `data/manifest.json` makes every
number deterministic (the app shows what the video shows), keeps the app up if Elexon is down,
and removes the need for a database or a scheduled job in v1. The script that produced it,
`scripts/fetch_elexon.py`, is in the repo and re-runs in about a minute. A live mode (daily
fetch into Postgres, e.g. Neon's free tier) is the first v2 item.

## 3. Scope: purchase decisions made in January, so delivery 2 January to 1 February

The brief limits the data to "purchase decisions to be made in January 2026". A day-ahead
decision made on day D-1 buys power for day D, so the decisions dated 1-31 January deliver on
2 January to 1 February (31 days). Scoring delivery days 1-31 January instead would include a
decision made on 31 December and drop one made on 31 January. December rows from 22 December are
loaded only as warm-up: they give the first days a persistence baseline and the trailing bias
adjustment its prior week, and they are never shown or scored. Runs published on 1 February are
in the snapshot only so that 1 February's hours have every lead time for the lead-time curve;
no January decision can select them.

## 4. The decision rule: newest run at or before the gate, per hour, inclusive, never filled

For each hour of delivery day D the app uses the WINDFOR row with the greatest `publishTime`
that is at or before the gate (default 09:20 UK on D-1, the EPEX 60-minute day-ahead auction;
N2EX 09:50 and the EPEX 30-minute 15:30 auction are presets). A run published exactly at the
gate counts. Selection is per target hour, not per run, so a newer run that omits an hour
cannot hide an older run's value. An hour with no eligible row stays empty and is counted in
coverage, never filled from a later run. The implementation is one `pandas.merge_asof` call
(`direction="backward"`, `allow_exact_matches=True`, `by="start_time"`), which keeps the whole
rule on one screen. Tests cover the inclusive boundary, a run one minute late, a missing hour,
golden days (15 Jan at 09:20 uses the 07:30Z run, at 09:50 the 09:30Z run, at 15:30 the 15:30Z
run), and a no-look-ahead property over every day and five gates.

## 5. UTC everywhere, Europe/London only at the edges

Timestamps are stored and joined in UTC. Europe/London is used in exactly three places: turning
a delivery day into its hourly start times, turning a gate into a UTC instant, and display. In
January GMT equals UTC, which would hide a timezone bug, so the tests also cover a BST date,
the 23-hour day of 29 March and the 25-hour day of 25 October 2026. A gate time that does not
exist on the spring clock change is refused rather than silently moved. The front end formats
every time with `Intl.DateTimeFormat` in Europe/London, so a viewer in any zone sees UK time.

## 6. Hourly block mean for alignment, with the alternative measured

FUELHH is half-hourly, WINDFOR hourly. The actual for forecast hour t is the mean of the two
half-hours in [t, t+1h), which matches the hourly blocks traded in the GB auctions and keeps
energy consistent. An hour with a missing half-hour is dropped, never guessed, and a duplicated
half-hour does not count as a complete hour. The alternative, matching the half-hour that starts
at t, is one API parameter away (`align=point`) and changes the MAE by a few tens of MW, which
is reported in the Scorecard so the conclusion does not rest on this choice.

## 7. Error metrics a desk can act on, with n beside every one

MAE is the "typical miss"; bias (forecast - actual, positive = forecast high = buyer short) is
reported with the share of hours over-forecast; the P90 of |error| is the cover size ("9 hours
in 10 the miss stayed under X"); the P90 of the signed error is the shortfall headroom ("plan X
less wind to be covered 9 hours in 10"); WAPE replaces MAPE because MAPE explodes in low-wind
hours. Every KPI carries its sample size and the coverage (hours scored over hours expected) so
a gap is never silent.

## 8. Persistence as the baseline, applied with the same availability rule

"Assume tomorrow's wind equals the last value I know" is the honest no-skill baseline. FUELHH
rows carry their own `publishTime` (normally the end of the period, occasionally later), so the
baseline uses the last half-hour that had been *published* by the gate, held flat across the
delivery day. Skill = 1 - MAE_forecast / MAE_persistence.

## 9. Empirical, leave-one-day-out bands with an out-of-sample check

The 80% band around a forecast is the 10th and 90th percentile of the signed error of every
(run, hour) pair in the window made at the same lead time (3-hour buckets), leaving the day
being shown out so a day never scores itself. Because the forecast reads high, the band for the
actual sits mostly below the line. Calibration is checked out of sample: quantiles from the
first half of the window, hit rate measured on the second half, and the hit rate is shown as a
KPI rather than assumed.

## 10. Bias adjustment with no look-ahead, as a correction not a model

The forecast reads about 1.7 GW high on average and still about 1.4 GW high when made 0-3 hours
ahead. Every WINDFOR run is a fixed block that starts at 21:00 UTC the previous evening, so about
a fifth of the rows describe hours that were already over when the run was published; the app never
selects or scores them as forecasts, but measured against the meter they read +1.67 GW high too,
the same size as the near-term forecasts, which is not what weather uncertainty would produce. That
points to a difference in what the two datasets count (WINDFOR: what the wind fleet could produce;
FUELHH: metered output after balancing actions such as curtailment) rather than forecasting skill.
The two datasets in scope cannot prove that, so it is stated as a hypothesis.
What a desk can do today is subtract the previous week's average miss, using only delivery days
D-8 to D-2, which are fully settled by the gate on D-1. That cuts the typical miss by about a
fifth and most of the bias, with zero leakage. It is labelled a correction of Elexon's forecast,
not a forecast of our own.

## 10b. Timing is judged by how often waiting pays, not only by the average

Elexon publishes 8 runs a day and the desk can trade at several deadlines, so the obvious question
is "when is the best time to buy?". The Timing screen scores every possible decision time on the
day before, which gives an average (09:50 is 1% better than 09:20, 15:30 is 8% better). The average
hides the day-by-day picture, so the app also compares the same days pairwise: 15:30 beat 09:20 on
only 16 of 31 days, and the median day gained 35 MW because a few large days carry the average.
It also shows which of the eight runs was closest on each day in hindsight (spread over all eight,
and even the latest run was the closest on only 9 days and the furthest on 4). Choosing the best run
every day would cut the miss by 24%, but that needs the actuals, so it is labelled an upper bound
and not a strategy. The app has no price data (the brief limits it to the two Elexon datasets), so
"best time" always means best forecast, never best price.

## 11. Anomaly flags, not an anomaly model

With one month of data a learned detector would only memorise that month. An hour is flagged
"unusual" when its absolute error is in the top 5% of the window; a day when its net energy
error is more than two standard deviations from the window's mean. Both rules can be checked by
hand, and both are shown on the calendar and in the tables rather than hidden in a score.

## 12. Three screens and URL state instead of a router

Decision Replay (what the desk saw, with a Reveal toggle), Scorecard (the whole window) and
Timing (is waiting worth it, and error against lead time), plus a Method & data drawer. Every
control lives in the URL query, so any view is a shareable link and the back button works with
no routing library. Charts follow a fixed colour order (blue forecast, orange actual, green
dashed bias-adjusted, grey later runs), carry a legend whenever two series are drawn, and each
has a table twin.

## 13. Vercel Python function first, container as the fallback

Vercel detects `app/main.py` with zero configuration; `vercel.json` only adds the npm build
command and excludes `node_modules`, tests and scripts from the function bundle. The Docker
image (multi-stage: Node builds the page, a slim Python image serves it as a non-root user with a
HEALTHCHECK) is the same code and is what a client would run on their own infrastructure. If the
Vercel preset ever misbehaves, the container runtime or a Render free service takes the same
image unchanged.

## Not built in v1, and why

**Chatbot.** Not asked for by the brief, and it would need an LLM API key (a secret on a
public-repo deployment plus a cost per question) inside a 16-hour budget. The useful part,
plain-English guidance for the buyer, is delivered as sentences generated from the computed
numbers, which cannot invent figures. v2: an assistant grounded in this app's own API (tools such
as "get the scorecard" and "replay this day"), so every number it quotes comes from the same
tested functions.

**Anomaly-detection model.** See decision 11. v2, with 12+ months and live data: a model of the
expected error given lead time, hour of day, wind level and season, used to raise alerts when a
new forecast run departs from it (large revisions, drifting error).

**Our own wind forecast.** The brief scopes the data to Elexon's forecasts and actuals, and the
job is to show and score them, not to replace them. v2 could blend weather-model wind speeds,
but beating the grid operator's forecast is a research project, not a pilot deliverable.

**Curtailment reconciliation.** The bias finding (decision 10) is a hypothesis. v2: pull Elexon
bid-offer acceptance volumes (BOAV), add curtailed MW back to the actual, and measure how much of
the bias disappears.

**Live mode.** A scheduled fetch into Postgres so the desk sees today's forecast for tomorrow,
with the same rule and the same scorecard rolling forward. This is where a database first earns
its place.
