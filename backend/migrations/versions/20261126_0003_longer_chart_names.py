"""make rankings.chart longer (32 -> 64 characters)

Why: Roblox has lists like "trending_in_roleplay_and_avatar_sim" (35 chars),
which didn't fit in 32. PostgreSQL refused to save them.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("rankings") as batch:
        batch.alter_column("chart", existing_type=sa.String(length=32), type_=sa.String(length=64),
                           existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("rankings") as batch:
        batch.alter_column("chart", existing_type=sa.String(length=64), type_=sa.String(length=32),
                           existing_nullable=False)
