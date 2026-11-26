"""
Database tables, written as Python classes (this is called an ORM).

  games            one row per game per platform. Name/icon stored ONCE.
  rankings         one row per game, per chart, per day. This is the history.
  collection_runs  one row per job run. Did it work? How many games? Errors?

  games 1 ──< many rankings      (one game has many daily ranks)
  collection_runs 1 ──< many rankings   (one run saves many ranks)

Primary key (id)  = unique number for each row.
Foreign key       = a column that points to a row in another table
                    (rankings.game_id -> games.id).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        # The same game can't be added twice for one platform
        UniqueConstraint("platform", "platform_game_id", name="uq_games_platform_game"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32))
    platform_game_id: Mapped[str] = mapped_column(String(64))   # Apple's / Roblox's own ID
    name: Mapped[str] = mapped_column(String(255))
    developer: Mapped[str | None] = mapped_column(String(255))
    genre: Mapped[str | None] = mapped_column(String(64))
    icon_url: Mapped[str | None] = mapped_column(Text)
    store_url: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    rankings: Mapped[list[Ranking]] = relationship(back_populates="game")


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))   # running / success / partial / failed
    trigger: Mapped[str] = mapped_column(String(16), default="manual")  # manual / scheduled
    games_collected: Mapped[int] = mapped_column(Integer, default=0)
    failed_platforms: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)


class Ranking(Base):
    __tablename__ = "rankings"
    __table_args__ = (
        # NO DUPLICATES: one game has only one rank per chart, country, device and day
        UniqueConstraint("game_id", "chart", "country", "device", "ranking_date", name="uq_rankings_game_chart_day"),
        # Index = like a book's index. Makes "show me today's chart" fast even with years of data
        Index("ix_rankings_chart_day", "chart", "country", "device", "ranking_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id", ondelete="SET NULL"))
    chart: Mapped[str] = mapped_column(String(64))   # Roblox names can be long: trending_in_roleplay_and_avatar_sim
    country: Mapped[str] = mapped_column(String(2))
    device: Mapped[str] = mapped_column(String(32), default="all", server_default="all")
    rank: Mapped[int] = mapped_column(Integer)
    player_count: Mapped[int | None] = mapped_column(Integer)
    ranking_date: Mapped[date] = mapped_column(Date)   # the day in IST
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    game: Mapped[Game] = relationship(back_populates="rankings")
