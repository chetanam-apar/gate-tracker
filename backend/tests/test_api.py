"""
Tests for the web API. Uses a temporary database with a little sample data.
TestClient = a fake browser that calls our API without starting a real server.
"""
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.main import app, get_db
from app.collectors.base import GameRank
from app.db import repository as repo
from app.db.models import Base
from app.db.session import session_scope

NOW = datetime(2026, 11, 26, tzinfo=timezone.utc)


def rank(r, gid, chart="top_free", platform="appstore", device="all"):
    return GameRank(platform=platform, chart=chart, country="in", device=device, rank=r,
                    game_id=gid, name=f"Game {gid}", collected_at=NOW)


@pytest.fixture
def client():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with session_scope(engine) as s:
        run = repo.start_run(s)
        repo.save_rankings(s, [rank(1, "a"), rank(2, "b")], date(2026, 11, 25))
        repo.save_rankings(s, [rank(1, "b"), rank(2, "a"),
                               rank(1, "r", "top_trending", "roblox", "computer")], date(2026, 11, 26))
        repo.finish_run(s, run, 5, [])

    def test_db():
        with session_scope(engine) as s:
            yield s

    app.dependency_overrides[get_db] = test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_list_charts(client):
    data = client.get("/api/charts").json()
    assert data["date"] == "2026-11-26"
    assert {(c["platform"], c["chart"]) for c in data["charts"]} == {("appstore", "top_free"), ("roblox", "top_trending")}


def test_get_chart_with_change(client):
    data = client.get("/api/charts/appstore/top_free").json()
    assert [(r["name"], r["change"]) for r in data["rows"]] == [("Game b", 1), ("Game a", -1)]


def test_roblox_defaults_to_computer(client):
    data = client.get("/api/charts/roblox/top_trending").json()
    assert data["device"] == "computer" and data["rows"][0]["name"] == "Game r"


def test_unknown_chart_is_404(client):
    response = client.get("/api/charts/appstore/nope")
    assert response.status_code == 404


def test_runs(client):
    runs = client.get("/api/runs").json()
    assert runs[0]["status"] == "success" and runs[0]["games_collected"] == 5
