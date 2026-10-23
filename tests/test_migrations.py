"""Tests for the Alembic migration."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_migration_upgrade_and_downgrade(tmp_path: Path, monkeypatch) -> None:
    """The initial migration creates and removes only its declared tables."""
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DEVMETER_DATABASE_URL", database_url)
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == {
        "alembic_version",
        "api_keys",
        "services",
        "usage_records",
    }

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
