"""
Alembic setup. You don't need to edit this file.

Migrations = version control for the database structure.
  alembic upgrade head    -> create / update tables to the latest version
  alembic downgrade -1    -> undo the last change
  alembic revision --autogenerate -m "add column x"  -> after changing models.py
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.db.models import Base
from app.db.session import get_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    # A URL passed with -x url=... wins (used by tests), else DATABASE_URL from .env
    return context.get_x_argument(as_dictionary=True).get("url") or get_database_url()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
