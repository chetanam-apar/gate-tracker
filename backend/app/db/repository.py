"""
All reading and writing of the database happens here (the "repository").

Why one file? The rest of the app never writes SQL or touches tables
directly. If we ever change the database, only this file changes.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.collectors.base import GameRank
from app.db.models import CollectionRun, Game, Ranking


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Run history ----------

def start_run(session: Session, trigger: str = "manual") -> CollectionRun:
    run = CollectionRun(started_at=_now(), status="running", trigger=trigger)
    session.add(run)
    session.flush()  # flush = send to DB now so run.id gets a number
    return run


def finish_run(session: Session, run: CollectionRun, games_collected: int,
               failed_platforms: list[str], error: str | None = None) -> None:
    run.finished_at = _now()
    run.games_collected = games_collected
    run.failed_platforms = ",".join(failed_platforms) or None
    run.error_message = error
    if error or (failed_platforms and games_collected == 0):
        run.status = "failed"
    elif failed_platforms:
        run.status = "partial"   # some platforms worked, some didn't
    else:
        run.status = "success"


# ---------- Saving rankings ----------

def _upsert_games(session: Session, platform: str, ranks: list[GameRank]) -> dict[str, Game]:
    """Insert new games, update name/icon of games we've seen before. Returns {platform_game_id: Game}."""
    ids = [r.game_id for r in ranks]
    existing = {
        g.platform_game_id: g
        for g in session.scalars(select(Game).where(Game.platform == platform, Game.platform_game_id.in_(ids)))
    }
    for r in ranks:
        game = existing.get(r.game_id)
        if game is None:
            game = Game(platform=platform, platform_game_id=r.game_id, first_seen_at=r.collected_at)
            session.add(game)
            existing[r.game_id] = game
        # Names and icons can change over time, keep the latest
        game.name = r.name
        game.developer = r.developer
        game.genre = r.genre or game.genre
        game.icon_url = r.icon_url
        game.store_url = r.store_url
        game.last_seen_at = r.collected_at
    session.flush()
    return existing


def save_rankings(session: Session, ranks: list[GameRank], ranking_date: date, run_id: int | None = None) -> int:
    """
    Save a list of GameRank for one day.

    No-duplicates rule: if this chart was already saved today, today's
    snapshot is REPLACED with the new one (delete + insert inside one
    transaction). So running 'collect' 3 times a day is safe.
    """
    groups: dict[tuple[str, str, str, str], list[GameRank]] = defaultdict(list)
    for r in ranks:
        groups[(r.platform, r.chart, r.country, r.device)].append(r)

    saved = 0
    for (platform, chart, country, device), group in groups.items():
        games = _upsert_games(session, platform, group)

        platform_game_ids = select(Game.id).where(Game.platform == platform)
        session.execute(
            delete(Ranking).where(
                Ranking.chart == chart,
                Ranking.country == country,
                Ranking.device == device,
                Ranking.ranking_date == ranking_date,
                Ranking.game_id.in_(platform_game_ids),
            )
        )
        seen: set[int] = set()
        for r in group:
            game = games[r.game_id]
            if game.id in seen:   # same game twice in one chart (rare API glitch): keep the best rank
                continue
            seen.add(game.id)
            session.add(Ranking(
                game_id=game.id, run_id=run_id, chart=chart, country=country, device=device, rank=r.rank,
                player_count=r.player_count, ranking_date=ranking_date, collected_at=r.collected_at,
            ))
            saved += 1
    session.flush()
    return saved


# ---------- Reading ----------

@dataclass
class ChartRow:
    rank: int
    name: str
    developer: str | None
    genre: str | None
    change: int | None      # +3 = moved up 3 places, -2 = down 2, None = new entry
    player_count: int | None
    game_id: int = 0
    icon_url: str | None = None
    store_url: str | None = None


def latest_date(session: Session, platform: str, chart: str, country: str, device: str = "all",
                before: date | None = None) -> date | None:
    query = (
        select(func.max(Ranking.ranking_date))
        .join(Game)
        .where(Game.platform == platform, Ranking.chart == chart, Ranking.country == country,
               Ranking.device == device)
    )
    if before:
        query = query.where(Ranking.ranking_date < before)
    return session.scalar(query)


def _ranks_on(session: Session, platform: str, chart: str, country: str, device: str,
              day: date) -> list[tuple[Ranking, Game]]:
    return list(session.execute(
        select(Ranking, Game).join(Game)
        .where(Game.platform == platform, Ranking.chart == chart, Ranking.country == country,
               Ranking.device == device, Ranking.ranking_date == day)
        .order_by(Ranking.rank)
    ).tuples())


def get_chart(session: Session, platform: str, chart: str, country: str, *, device: str = "all",
              day: date | None = None) -> tuple[date | None, list[ChartRow]]:
    """A chart for one day, with rank change compared to the previous saved day."""
    day = day or latest_date(session, platform, chart, country, device)
    if day is None:
        return None, []
    previous_day = latest_date(session, platform, chart, country, device, before=day)
    previous = {}
    if previous_day:
        previous = {rk.game_id: rk.rank
                    for rk, _ in _ranks_on(session, platform, chart, country, device, previous_day)}

    rows = []
    for rk, game in _ranks_on(session, platform, chart, country, device, day):
        old = previous.get(rk.game_id)
        rows.append(ChartRow(rank=rk.rank, name=game.name, developer=game.developer, genre=game.genre,
                             change=(old - rk.rank) if old is not None else None,
                             player_count=rk.player_count, game_id=game.id,
                             icon_url=game.icon_url, store_url=game.store_url))
    return day, rows


@dataclass
class ChartInfo:
    platform: str
    chart: str
    country: str
    device: str
    games: int


def list_charts(session: Session, day: date | None = None) -> tuple[date | None, list[ChartInfo]]:
    """Every chart saved on a day (default: the latest day with any data)."""
    day = day or session.scalar(select(func.max(Ranking.ranking_date)))
    if day is None:
        return None, []
    rows = session.execute(
        select(Game.platform, Ranking.chart, Ranking.country, Ranking.device, func.count())
        .join(Game).where(Ranking.ranking_date == day)
        .group_by(Game.platform, Ranking.chart, Ranking.country, Ranking.device)
        .order_by(Game.platform, Ranking.device, Ranking.chart)
    ).all()
    return day, [ChartInfo(*row) for row in rows]


def recent_runs(session: Session, limit: int = 10) -> list[CollectionRun]:
    return list(session.scalars(select(CollectionRun).order_by(CollectionRun.id.desc()).limit(limit)))


# ---------- History ----------

def available_dates(session: Session, platform: str, chart: str, country: str, device: str = "all") -> list[date]:
    """Every day this chart has data, newest first. Used by the date dropdown."""
    return list(session.scalars(
        select(Ranking.ranking_date).distinct().join(Game)
        .where(Game.platform == platform, Ranking.chart == chart, Ranking.country == country,
               Ranking.device == device)
        .order_by(Ranking.ranking_date.desc())
    ))


@dataclass
class GenrePoint:
    day: date
    genre: str
    players: int     # total live players of all games of this genre in the chart
    games: int       # how many games of this genre are in the chart


def genre_trend(session: Session, platform: str, chart: str, country: str, device: str,
                since: date | None = None) -> list[GenrePoint]:
    """Per day and per genre: total players and number of games. For the genre graph."""
    genre = func.coalesce(Game.genre, "Unknown")
    query = (
        select(Ranking.ranking_date, genre, func.coalesce(func.sum(Ranking.player_count), 0), func.count())
        .join(Game)
        .where(Game.platform == platform, Ranking.chart == chart, Ranking.country == country,
               Ranking.device == device)
        .group_by(Ranking.ranking_date, genre)
        .order_by(Ranking.ranking_date)
    )
    if since:
        query = query.where(Ranking.ranking_date >= since)
    return [GenrePoint(day=d, genre=g, players=int(p), games=n) for d, g, p, n in session.execute(query)]
