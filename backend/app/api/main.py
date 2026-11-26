"""
The web API. The website (Step 6) calls these addresses to get data as JSON.

Run it (from backend/):
    uvicorn app.api.main:app --reload
Then open in your browser:
    http://127.0.0.1:8000/docs     <- a test page where you can try every address

How a request works:
    browser asks  GET /api/charts/roblox/top_trending?device=computer
    -> FastAPI calls the matching function below
    -> the function reads the database (through repository.py)
    -> FastAPI turns the result into JSON and sends it back
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import repository as repo
from app.db.session import session_scope

app = FastAPI(
    title="Game Tracker API",
    description="Top games in India on the App Store, Play Store and Roblox, saved every day.",
    version="0.1.0",
)

# CORS: lets the website (running on another port while developing) call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_db() -> Iterator[Session]:
    """Gives each request its own database session, closed automatically after."""
    with session_scope() as session:
        yield session


# ---------- Response shapes (what the JSON looks like) ----------

class ChartSummary(BaseModel):
    platform: str
    chart: str
    country: str
    device: str
    games: int


class ChartList(BaseModel):
    date: date | None
    charts: list[ChartSummary]


class ChartRowOut(BaseModel):
    rank: int
    change: int | None          # +3 up, -2 down, null = new today
    game_id: int
    name: str
    developer: str | None
    genre: str | None
    player_count: int | None
    icon_url: str | None
    store_url: str | None


class ChartOut(BaseModel):
    platform: str
    chart: str
    country: str
    device: str
    date: date
    rows: list[ChartRowOut]


class RunOut(BaseModel):
    id: int
    started_at: str
    finished_at: str | None
    status: str
    trigger: str
    games_collected: int
    failed_platforms: str | None


# ---------- Addresses ----------

@app.get("/api/health", tags=["system"])
def health(db: Session = Depends(get_db)) -> dict:
    """Is the API running and can it reach the database?"""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/charts", response_model=ChartList, tags=["charts"])
def list_charts(day: date | None = Query(None, alias="date", description="YYYY-MM-DD. Default: latest"),
                db: Session = Depends(get_db)):
    """Every chart saved on a day."""
    found_day, charts = repo.list_charts(db, day)
    return ChartList(date=found_day, charts=[ChartSummary(**vars(c)) for c in charts])


@app.get("/api/charts/{platform}/{chart}", response_model=ChartOut, tags=["charts"])
def get_chart(platform: str, chart: str,
              device: str | None = Query(None, description="Roblox: computer / high_end_phone"),
              country: str | None = Query(None, description="Default: from config.yaml"),
              day: date | None = Query(None, alias="date", description="YYYY-MM-DD. Default: latest"),
              limit: int = Query(50, ge=1, le=200),
              db: Session = Depends(get_db)):
    """One chart for one day, with rank change compared to the previous day."""
    country = country or get_settings().defaults.country
    device = device or ("computer" if platform == "roblox" else "all")
    found_day, rows = repo.get_chart(db, platform, chart, country, device=device, day=day)
    if not rows:
        raise HTTPException(404, f"No data for {platform}/{chart}/{country}/{device}. See /api/charts")
    return ChartOut(platform=platform, chart=chart, country=country, device=device, date=found_day,
                    rows=[ChartRowOut(**vars(r)) for r in rows[:limit]])


@app.get("/api/runs", response_model=list[RunOut], tags=["system"])
def list_runs(limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    """History of collection runs: did last night's job work?"""
    return [RunOut(id=r.id, started_at=r.started_at.isoformat(),
                   finished_at=r.finished_at.isoformat() if r.finished_at else None,
                   status=r.status, trigger=r.trigger, games_collected=r.games_collected,
                   failed_platforms=r.failed_platforms)
            for r in repo.recent_runs(db, limit)]
