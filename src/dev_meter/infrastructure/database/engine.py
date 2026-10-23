"""SQLAlchemy engine and session-factory construction."""

from collections.abc import Callable
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str) -> Engine:
    """Create a configured SQLAlchemy engine without opening a connection."""
    engine_options: dict[str, Any] = {
        "future": True,
        "pool_pre_ping": True,
    }
    if database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}

    return create_engine(database_url, **engine_options)


def create_session_factory(engine: Engine) -> Callable[[], Session]:
    """Create a factory for short-lived database sessions."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
