"""FastAPI entry point.

One app serves two things:
- the JSON API under /api (routes declared below), and
- the built React front end from frontend/dist at / (everything else).

The same object runs under uvicorn in dev and Docker, and as a Vercel Python function in
production, so there is exactly one code path to test. Routes only parse parameters and
serialise results; the computation lives in app.desk.
"""

from datetime import date, time
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response

from app import __version__, desk, schemas

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = ROOT / "frontend" / "dist"

# The snapshot never changes, so every data response can be cached by the CDN for a day and
# served stale while a fresh copy is fetched.
CACHE_CONTROL = "public, max-age=300, s-maxage=86400, stale-while-revalidate=604800"

app = FastAPI(
    title="Day-Ahead Wind Desk API",
    version=__version__,
    description=(
        "GB wind forecast (Elexon WINDFOR) as available at day-ahead gate closure, scored "
        "against actual wind output (Elexon FUELHH) for January 2026."
    ),
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

GateParam = Annotated[
    str,
    Query(
        pattern=r"^\d{2}:\d{2}$",
        description="Decision time, HH:MM UK local time on the day before delivery.",
    ),
]
AlignParam = Annotated[
    schemas.Alignment,
    Query(description="How half-hourly actuals map to forecast hours: block mean or point."),
]


def _gate(text: str) -> time:
    try:
        t = desk.parse_gate(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not (0 <= t.hour < 24 and 0 <= t.minute < 60):
        raise HTTPException(status_code=422, detail="gate must be a valid HH:MM time")
    return t


def _cached(response: Response) -> None:
    response.headers["Cache-Control"] = CACHE_CONTROL


@app.get("/api/health", response_model=schemas.Health, tags=["meta"])
def health() -> dict:
    """Liveness check used by Docker's HEALTHCHECK, CI and the landing page."""
    return {"status": "ok", "app": "day-ahead-wind-desk", "version": __version__}


@app.get("/api/meta", response_model=schemas.Meta, tags=["meta"])
def meta(response: Response) -> dict:
    """Data window, gate presets, snapshot provenance (sources, row counts, hashes)."""
    _cached(response)
    return desk.meta()


@app.get("/api/decision", response_model=schemas.Replay, tags=["analysis"])
def decision(
    response: Response,
    date_: Annotated[
        date, Query(alias="date", description="Delivery day, 2026-01-02 to 2026-02-01")
    ],
    gate: GateParam = "09:20",
    align: AlignParam = "block",
) -> dict:
    """Decision Replay: the forecast the desk could see at the gate for one delivery day, its
    empirical band, the runs published later, and what actually happened."""
    try:
        result = desk.replay(date_, _gate(gate), align)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _cached(response)
    return result


@app.get("/api/scorecard", response_model=schemas.Scorecard, tags=["analysis"])
def scorecard(response: Response, gate: GateParam = "09:20", align: AlignParam = "block") -> dict:
    """January scorecard for one gate policy: KPIs, per-day and per-hour breakdowns, the error
    histogram, the worst days and hours, and plain-language buying guidance."""
    _cached(response)
    return desk.scorecard(_gate(gate), align)


@app.get("/api/timing", response_model=schemas.Timing, tags=["analysis"])
def timing(response: Response, align: AlignParam = "block") -> dict:
    """Value of waiting: January MAE and P90 for every half-hour gate on the day before."""
    _cached(response)
    return desk.timing(align)


@app.get("/api/waiting", response_model=schemas.Waiting, tags=["analysis"])
def waiting(response: Response, align: AlignParam = "block") -> dict:
    """How often deciding later pays, day by day, plus the best run in hindsight (an upper
    bound that needs the actuals, so it is not actionable)."""
    _cached(response)
    return desk.waiting(align)


@app.get("/api/leadtime", response_model=schemas.LeadTime, tags=["analysis"])
def leadtime(response: Response, align: AlignParam = "block") -> dict:
    """Error against lead time over every (run, target) pair, in 3-hour buckets."""
    _cached(response)
    return desk.leadtime(align)


# The front end is registered last. FastAPI >= 0.138 gives API routes priority over
# frontend files whatever the order; check_dir=False lets the app import (and the API
# tests run) before `npm run build` has produced frontend/dist.
app.frontend("/", directory=FRONTEND_DIST, check_dir=False)
