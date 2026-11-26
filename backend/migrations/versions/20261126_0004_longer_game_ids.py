"""make games.platform_game_id longer (64 -> 255 characters)

Why: Play Store IDs are Android package names, which can be long
(up to 255 characters). Some top games had IDs longer than 64.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("games") as batch:
        batch.alter_column("platform_game_id", existing_type=sa.String(length=64), type_=sa.String(length=255),
                           existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("games") as batch:
        batch.alter_column("platform_game_id", existing_type=sa.String(length=255), type_=sa.String(length=64),
                           existing_nullable=False)
