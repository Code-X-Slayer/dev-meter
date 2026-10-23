"""FastAPI application construction."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from dev_meter.api.analytics_routes import router as analytics_router
from dev_meter.api.auth_routes import router as auth_router
from dev_meter.api.gateway_routes import router as gateway_router
from dev_meter.api.routes import router
from dev_meter.core.config import Settings
from dev_meter.infrastructure.database.lifecycle import database_lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the DevMeter application."""
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        async with database_lifespan(application, config):
            yield

    application = FastAPI(
        title=config.application_name,
        debug=config.debug,
        lifespan=lifespan,
    )
    application.state.settings = config
    application.state.default_request_limit = config.default_request_limit
    application.include_router(router)
    application.include_router(gateway_router)
    application.include_router(analytics_router)
    application.include_router(auth_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        """Report whether the application is alive."""
        return {"status": "ok"}

    return application


app = create_app()
