"""
Database connection.

engine   = the connection to the database (opened once, reused)
session  = one "conversation" with the database. We open it, do our
           work, then commit (save) or rollback (undo everything).
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


class DatabaseNotConfigured(Exception):
    pass


def get_database_url() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise DatabaseNotConfigured("DATABASE_URL is missing. Add it to your .env file (see .env.example)")
    return url


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping: check the connection is alive before using it
    return create_engine(get_database_url(), pool_pre_ping=True)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """
    Use like:  with session_scope() as session: ...
    If anything fails inside, NOTHING is saved (rollback).
    So we never end up with half of a chart saved.
    """
    factory = sessionmaker(bind=engine or get_engine(), expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
