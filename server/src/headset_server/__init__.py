import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import api, ws
from .auth import Auth
from .commands import Commands
from .config import Settings
from .db import make_engine, make_session_factory
from .live import LiveHub
from .migrations import run_migrations
from .registry import Registry
from .sessions import Sessions
from .setup_tools import SetupJobs

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Миграции Alembic — синхронный код со своим event loop, поэтому в отдельном потоке
        await asyncio.to_thread(run_migrations, settings.database_url)

        engine = make_engine(settings.database_url)
        session_factory = make_session_factory(engine)
        hub = LiveHub()
        sessions = Sessions(session_factory, settings.session_grace_s)
        await sessions.recover()
        registry = Registry(session_factory, hub, settings, sessions)
        await registry.load()

        app.state.settings = settings
        app.state.auth = Auth(Path(settings.auth_file))
        app.state.session_factory = session_factory
        app.state.hub = hub
        app.state.registry = registry
        commands = Commands(session_factory, registry, hub, sessions)
        app.state.commands = commands
        app.state.sessions = sessions

        async def register_for_setup(label: str, serial: str, android_id: str | None) -> tuple[str, str]:
            creds = await api.register(app.state, label, serial, android_id)
            return creds.headset_id, creds.token

        app.state.setup_jobs = SetupJobs(register_for_setup, settings.port)

        tasks = [
            asyncio.create_task(_every(1.0, registry.sweep)),
            asyncio.create_task(_every(1.0, commands.sweep)),
            asyncio.create_task(_every(1.0, sessions.tick)),
            asyncio.create_task(_every(settings.state_snapshot_s, registry.persist)),
        ]
        try:
            yield
        finally:
            for t in tasks:
                t.cancel()
            for t in tasks:
                with suppress(asyncio.CancelledError):
                    await t
            await sessions.shutdown()
            await registry.shutdown()
            await engine.dispose()

    app = FastAPI(title="Headset Manager", version="0.1.0", lifespan=lifespan)
    app.include_router(api.router)
    app.include_router(ws.router)

    # Дашборд — последним, чтобы не перекрыть /api, /live и /agent
    dashboard = Path(settings.dashboard_dir)
    if dashboard.is_dir():
        app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")
    else:
        log.info("dashboard not built (%s), serving API only", dashboard)
    return app


async def _every(seconds: float, fn: Callable[[], Awaitable[None]]) -> None:
    while True:
        await asyncio.sleep(seconds)
        try:
            await fn()
        except Exception:
            log.exception("periodic task %s failed", fn.__name__)


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=logging.INFO)
    # Строго один процесс: онлайн-шлемы и их соединения живут в памяти
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, workers=1)
