"""Uvicorn server entry point for local and hosted execution."""

import os

import uvicorn

from dev_meter.core.config import Settings


def main() -> None:
    """Run the DevMeter server using environment-provided runtime settings."""
    settings = Settings()
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "dev_meter.app:app",
        host="0.0.0.0",
        port=port,
        reload=settings.environment == "development",
    )


if __name__ == "__main__":
    main()
