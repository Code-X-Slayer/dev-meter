"""Tests for SQLAlchemy database infrastructure."""

from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from dev_meter.infrastructure.database.base import Base
from dev_meter.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
)
from dev_meter.infrastructure.database.session import get_db_session


def test_engine_and_session_factory_use_isolated_sqlite_database(
    tmp_path: Path,
) -> None:
    """The infrastructure can construct a real isolated SQLite session."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"

    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        assert isinstance(session, Session)
        assert session.bind is engine

    engine.dispose()


def test_session_dependency_closes_session() -> None:
    """The request dependency closes its session during generator cleanup."""

    class TrackingSession(Session):
        closed = False

        def close(self) -> None:
            self.closed = True
            super().close()

    engine = create_engine("sqlite:///:memory:")
    session_factory = create_session_factory(engine)
    session_factory.class_ = TrackingSession
    application = FastAPI()
    application.state.session_factory = session_factory
    request = type("RequestStub", (), {"app": application})()
    dependency = get_db_session(request)

    session = next(dependency)
    assert isinstance(session, TrackingSession)
    assert session.closed is False

    dependency.close()

    assert session.closed is True
    engine.dispose()


def test_base_has_no_product_tables() -> None:
    """The metadata contains only the current product tables."""
    assert set(Base.metadata.tables) == {
        "services",
        "api_keys",
        "usage_records",
    }
