import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from headset_server.db import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or os.environ.get(
        "HM_DATABASE_URL", "sqlite+aiosqlite:///./headsets.db"
    )


def _configure(connection=None) -> None:
    # render_as_batch: SQLite не умеет большинство ALTER TABLE, Alembic пересоздаёт таблицу
    context.configure(
        connection=connection,
        url=None if connection is not None else _url(),
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )


def run_migrations_offline() -> None:
    _configure()
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
