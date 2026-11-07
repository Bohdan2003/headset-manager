import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from .db import GameSession, HeadsetState, utcnow

log = logging.getLogger(__name__)

AGENT_PACKAGE = "com.arena.agent"
SYSTEM_PREFIXES = ("com.oculus.", "com.meta.", "com.facebook.", "com.android.", "android")


def is_game(pkg: str | None) -> bool:
    return bool(pkg) and pkg != AGENT_PACKAGE and not pkg.startswith(SYSTEM_PREFIXES)


@dataclass
class _Active:
    row_id: int
    headset_id: str
    package: str
    started_at: datetime
    paused_at: datetime | None = None  # игрок вышел; если не вернётся за grace — сессия закончилась
    exits: int = 0
    guard_returns: int = 0


class Sessions:
    """
    Учёт сессий игр по смене текущего приложения. Держит открытые сессии в памяти,
    каждое изменение сразу пишет в БД (сессий мало — десятки в день на шлем).
    """

    def __init__(self, session_factory: async_sessionmaker, grace_s: int) -> None:
        self._sf = session_factory
        self._grace = timedelta(seconds=grace_s)
        self._active: dict[str, _Active] = {}
        # После «закрыть игру» агент ещё секунду-две может присылать старую игру в heartbeat —
        # не открываем из-за этого новую сессию
        self._suppress: dict[str, tuple[str, datetime]] = {}

    async def recover(self) -> None:
        """После перезапуска сервера: незакрытые сессии заканчиваем последним сигналом шлема."""
        async with self._sf() as s:
            rows = (await s.execute(select(GameSession).where(GameSession.ended_at.is_(None)))).scalars().all()
            for row in rows:
                state = await s.get(HeadsetState, row.headset_id)
                last = _as_utc(state.last_seen) if state and state.last_seen else None
                row.ended_at = max(last, _as_utc(row.started_at)) if last else _as_utc(row.started_at)
                row.end_reason = "server_restart"
            await s.commit()
        if rows:
            log.info("closed %d sessions left open before restart", len(rows))

    async def on_app(self, headset_id: str, pkg: str | None) -> None:
        now = utcnow()
        active = self._active.get(headset_id)
        if active is not None:
            if pkg == active.package:
                if active.paused_at is not None:  # вернулся в ту же игру — сессия продолжается
                    active.paused_at = None
                    await self._save(active)
                return
            if not is_game(pkg):
                if active.paused_at is None:  # вышел в меню Meta / наше меню — ждём возврата
                    active.paused_at = now
                    active.exits += 1
                    await self._save(active)
                return
            # запущена другая игра
            await self._close(active, active.paused_at or now, "switched")
        if is_game(pkg):
            suppressed = self._suppress.get(headset_id)
            if suppressed and suppressed[0] == pkg and suppressed[1] > now:
                return
            await self._open(headset_id, pkg, now)

    async def on_guard_return(self, headset_id: str) -> None:
        active = self._active.get(headset_id)
        if active is not None:
            active.guard_returns += 1
            await self._save(active)

    async def end(self, headset_id: str, reason: str) -> None:
        """Оператор закрыл или перезапустил игру, вывел в меню; шлем пропал из сети."""
        active = self._active.get(headset_id)
        if active is not None:
            now = utcnow()
            if reason in ("closed", "menu"):
                self._suppress[headset_id] = (active.package, now + timedelta(seconds=10))
            if active.paused_at is not None:
                active.exits -= 1  # выход, после которого сессия закончилась, — не «выход с возвратом»
            await self._close(active, active.paused_at or now, reason)

    async def tick(self) -> None:
        """Игрок вышел и не вернулся за grace — сессия закончилась в момент выхода."""
        limit = utcnow() - self._grace
        for active in list(self._active.values()):
            if active.paused_at is not None and active.paused_at < limit:
                active.exits -= 1  # последний выход — это конец сессии, а не «выход с возвратом»
                await self._close(active, active.paused_at, "exited")

    async def shutdown(self) -> None:
        for active in list(self._active.values()):
            await self._close(active, active.paused_at or utcnow(), "server_shutdown")

    async def _open(self, headset_id: str, pkg: str, now: datetime) -> None:
        async with self._sf() as s:
            row = GameSession(headset_id=headset_id, package=pkg, started_at=now, exits=0, guard_returns=0)
            s.add(row)
            await s.commit()
            self._active[headset_id] = _Active(row.id, headset_id, pkg, now)

    async def _close(self, active: _Active, ended_at: datetime, reason: str) -> None:
        self._active.pop(active.headset_id, None)
        async with self._sf() as s:
            row = await s.get(GameSession, active.row_id)
            if row is not None:
                row.ended_at = ended_at
                row.end_reason = reason
                row.exits = max(0, active.exits)
                row.guard_returns = active.guard_returns
                await s.commit()

    async def _save(self, active: _Active) -> None:
        async with self._sf() as s:
            row = await s.get(GameSession, active.row_id)
            if row is not None:
                row.exits = max(0, active.exits)
                row.guard_returns = active.guard_returns
                await s.commit()


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
