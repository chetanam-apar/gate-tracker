"""add device to rankings and genre to games

Why: Roblox charts are different on phone vs computer, so one game can
have 2 ranks in the same chart on the same day. We add a "device" column
and include it in the no-duplicates rule.

Existing rows (App Store) get device = "all".

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("games", sa.Column("genre", sa.String(length=64), nullable=True))

    # batch_alter_table works on both PostgreSQL and SQLite (used in tests)
    with op.batch_alter_table("rankings") as batch:
        batch.add_column(sa.Column("device", sa.String(length=32), nullable=False, server_default="all"))
        batch.drop_constraint("uq_rankings_game_chart_day", type_="unique")
        batch.create_unique_constraint(
            "uq_rankings_game_chart_day", ["game_id", "chart", "country", "device", "ranking_date"]
        )
        batch.drop_index("ix_rankings_chart_day")
        batch.create_index("ix_rankings_chart_day", ["chart", "country", "device", "ranking_date"])


def downgrade() -> None:
    # Without "device", phone and computer rows of the same game would clash.
    # Keep only one row per game/chart/country/day before restoring the old rule.
    op.execute(
        "DELETE FROM rankings WHERE id NOT IN ("
        "SELECT MIN(id) FROM rankings GROUP BY game_id, chart, country, ranking_date)"
    )
    with op.batch_alter_table("rankings") as batch:
        batch.drop_index("ix_rankings_chart_day")
        batch.create_index("ix_rankings_chart_day", ["chart", "country", "ranking_date"])
        batch.drop_constraint("uq_rankings_game_chart_day", type_="unique")
        batch.create_unique_constraint("uq_rankings_game_chart_day", ["game_id", "chart", "country", "ranking_date"])
        batch.drop_column("device")
    op.drop_column("games", "genre")
