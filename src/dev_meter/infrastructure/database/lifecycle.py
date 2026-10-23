"""Application lifecycle management for database resources."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from dev_meter.core.config import Settings
from dev_meter.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
)


@asynccontextmanager
async def database_lifespan(
    application: FastAPI,
    settings: Settings,
) -> AsyncIterator[None]:
    """Own the application engine for the duration of its lifespan."""
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    http_client = httpx.AsyncClient(timeout=settings.upstream_timeout)
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.http_client = http_client
    try:
        yield
    finally:
        await http_client.aclose()
        engine.dispose()


def get_application_engine(application: FastAPI) -> Engine:
    """Return the engine owned by a running application."""
    return application.state.engine


def get_application_session_factory(
    application: FastAPI,
) -> sessionmaker[Session]:
    """Return the session factory owned by a running application."""
    return application.state.session_factory
