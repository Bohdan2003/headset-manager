from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).resolve().parent


def alembic_config(database_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def run_migrations(database_url: str) -> None:
    """Привести схему БД к последней версии. Вызывается при каждом старте сервера."""
    command.upgrade(alembic_config(database_url), "head")
