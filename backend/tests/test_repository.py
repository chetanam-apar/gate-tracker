"""
Tests for saving and reading rankings.

Uses SQLite in memory (a tiny database that lives only during the test),
so these run without Docker and finish in under a second.
The real app uses PostgreSQL. Our code works on both because we use SQLAlchemy.
"""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

from app.collectors.base import GameRank
from app.db import repository as repo
from app.db.models import Base, Game, Ranking
from app.db.session import session_scope

DAY1, DAY2 = date(2026, 11, 26), date(2026, 11, 27)
NOW = datetime(2026, 11, 26, 18, 30, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return eng


def make(rank, gid, name=None, chart="top_free", platform="appstore"):
    return GameRank(platform=platform, chart=chart, country="in", rank=rank,
                    game_id=gid, name=name or f"Game {gid}", collected_at=NOW)


def count(engine, model):
    with session_scope(engine) as s:
        return s.scalar(select(func.count()).select_from(model))


def test_running_twice_same_day_makes_no_duplicates(engine):
    chart = [make(1, "a"), make(2, "b"), make(3, "c")]
    for _ in range(3):
        with session_scope(engine) as s:
            repo.save_rankings(s, chart, DAY1)
    assert count(engine, Ranking) == 3
    assert count(engine, Game) == 3


def test_rerun_replaces_todays_snapshot(engine):
    with session_scope(engine) as s:
        repo.save_rankings(s, [make(1, "a"), make(2, "b"), make(3, "c")], DAY1)
    # Later the same day: "c" dropped out, "d" came in, order changed
    with session_scope(engine) as s:
        repo.save_rankings(s, [make(1, "b"), make(2, "a"), make(3, "d")], DAY1)
    with session_scope(engine) as s:
        _, rows = repo.get_chart(s, "appstore", "top_free", "in", DAY1)
    assert [r.name for r in rows] == ["Game b", "Game a", "Game d"]


def test_rank_change_compared_to_previous_day(engine):
    with session_scope(engine) as s:
        repo.save_rankings(s, [make(1, "a"), make(2, "b"), make(3, "c")], DAY1)
        repo.save_rankings(s, [make(1, "c"), make(2, "a"), make(3, "new")], DAY2)
    with session_scope(engine) as s:
        day, rows = repo.get_chart(s, "appstore", "top_free", "in")  # latest day
    assert day == DAY2
    changes = {r.name: r.change for r in rows}
    assert changes == {"Game c": 2, "Game a": -1, "Game new": None}  # up 2, down 1, NEW


def test_game_name_updates_but_game_stays_one_row(engine):
    with session_scope(engine) as s:
        repo.save_rankings(s, [make(1, "a", "Old Name")], DAY1)
        repo.save_rankings(s, [make(1, "a", "New Name")], DAY2)
    with session_scope(engine) as s:
        games = s.scalars(select(Game)).all()
    assert len(games) == 1 and games[0].name == "New Name"


def test_same_chart_name_on_two_platforms_does_not_clash(engine):
    with session_scope(engine) as s:
        repo.save_rankings(s, [make(1, "x", platform="appstore")], DAY1)
        repo.save_rankings(s, [make(1, "x", platform="playstore")], DAY1)
    assert count(engine, Ranking) == 2  # saving Play Store didn't delete App Store's top_free


def test_run_status(engine):
    with session_scope(engine) as s:
        ok, partial, failed = repo.start_run(s), repo.start_run(s), repo.start_run(s)
        repo.finish_run(s, ok, 150, [])
        repo.finish_run(s, partial, 100, ["roblox"])
        repo.finish_run(s, failed, 0, ["appstore", "roblox"])
        assert (ok.status, partial.status, failed.status) == ("success", "partial", "failed")
        assert partial.failed_platforms == "roblox"
