import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import WebSocket
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from .config import Settings
from .db import Event, Headset, HeadsetApp, HeadsetState, utcnow
from .live import LiveHub
from .protocol import AppInfo, Heartbeat, Hello, HeadsetView, LiveHeadset, ProtocolModel, UpdateProgress
from .sessions import Sessions

log = logging.getLogger(__name__)

# Коды закрытия WebSocket (4000–4999 — для приложений)
CLOSE_REPLACED = 4409  # шлем подключился заново, старое соединение больше не нужно
CLOSE_TIMEOUT = 4408   # от шлема давно ничего не приходило


class Registry:
    """
    Состояние всех шлемов в памяти процесса: кто онлайн, батарея, текущая игра.
    Изменения сразу рассылаются дашборду, а в БД сохраняются снимком раз в state_snapshot_s.
    События (подключение, смена игры, батарея) пишутся в журнал сразу.
    """

    def __init__(
        self, session_factory: async_sessionmaker, hub: LiveHub, settings: Settings, sessions: Sessions
    ) -> None:
        self._sf = session_factory
        self._sessions = sessions
        self._hub = hub
        self._settings = settings
        self._views: dict[str, HeadsetView] = {}
        self._sockets: dict[str, WebSocket] = {}
        self._dirty: set[str] = set()

    async def load(self) -> None:
        """При старте сервера все шлемы офлайн, пока не подключатся сами."""
        async with self._sf() as s:
            rows = (await s.execute(select(Headset, HeadsetState).outerjoin(HeadsetState))).all()
            apps = (await s.execute(select(HeadsetApp).order_by(HeadsetApp.title))).scalars().all()
        apps_by_headset: dict[str, list[AppInfo]] = {}
        for app in apps:
            apps_by_headset.setdefault(app.headset_id, []).append(
                AppInfo(package=app.package, title=app.title, vr=app.vr)
            )
        for headset, state in rows:
            view = HeadsetView(id=headset.id, label=headset.label, serial=headset.serial)
            if state is not None:
                view = view.model_copy(
                    update={
                        "battery": state.battery,
                        "charging": state.charging,
                        "temp": state.temp,
                        "current_pkg": state.current_pkg,
                        "adb": state.adb,
                        "sleep_disabled": state.sleep_disabled,
                        "agent_version": state.agent_version,
                        "last_seen": _as_utc(state.last_seen),
                        "guard_pkg": state.guard_pkg,
                    }
                )
            view.apps = apps_by_headset.get(headset.id, [])
            self._views[headset.id] = view
            self._dirty.add(headset.id)

    def is_online(self, headset_id: str) -> bool:
        return headset_id in self._sockets

    def is_asleep(self, headset_id: str) -> bool:
        return self._views[headset_id].screen_on is False

    def exists(self, headset_id: str) -> bool:
        return headset_id in self._views

    async def send(self, headset_id: str, message: ProtocolModel) -> bool:
        """Отправить сообщение агенту. False — шлем офлайн или соединение оборвалось."""
        ws = self._sockets.get(headset_id)
        if ws is None:
            return False
        try:
            await ws.send_text(message.to_json())
            return True
        except Exception:
            log.info("send to %s failed", headset_id)
            return False

    async def set_update(self, headset_id: str, update: UpdateProgress | None) -> None:
        self._views[headset_id].update = update
        await self._publish(headset_id)

    async def set_apps(self, headset_id: str, apps: list[AppInfo]) -> None:
        """Агент прислал список установленных игр — заменяем целиком."""
        unique = {a.package: a for a in apps}
        async with self._sf() as s:
            await s.execute(delete(HeadsetApp).where(HeadsetApp.headset_id == headset_id))
            s.add_all(
                HeadsetApp(headset_id=headset_id, package=a.package, title=a.title, vr=a.vr) for a in unique.values()
            )
            await s.commit()
        self._views[headset_id].apps = sorted(unique.values(), key=lambda a: a.title.lower())
        await self._publish(headset_id)

    def snapshot(self) -> list[HeadsetView]:
        return sorted(self._views.values(), key=lambda v: v.label)

    async def upsert(self, headset: Headset) -> None:
        """Шлем зарегистрирован или перенастроен через API."""
        view = self._views.get(headset.id)
        if view is None:
            view = HeadsetView(id=headset.id, label=headset.label, serial=headset.serial)
        else:
            view.label = headset.label
        self._views[headset.id] = view
        await self._publish(headset.id)

    async def connect(self, headset_id: str, ws: WebSocket, hello: Hello) -> None:
        old = self._sockets.get(headset_id)
        self._sockets[headset_id] = ws
        if old is not None and old is not ws:
            await _close_quietly(old, CLOSE_REPLACED)

        view = self._views[headset_id]
        view.online = True
        view.agent_version = hello.agent_version
        view.update = None  # агент перезапустился: обновление, если оно шло, закончилось
        view.last_seen = utcnow()
        await self.log_event(headset_id, "connect", {"agentVersion": hello.agent_version})
        await self._publish(headset_id)

    def touch(self, headset_id: str) -> None:
        """Любое сообщение от агента продлевает «онлайн»."""
        self._views[headset_id].last_seen = utcnow()

    async def heartbeat(self, headset_id: str, hb: Heartbeat) -> None:
        view = self._views[headset_id]
        if hb.battery != view.battery:
            await self.log_event(
                headset_id, "battery", {"level": hb.battery, "charging": hb.charging, "screenOn": hb.screen_on}
            )
        if view.charging is not None and hb.charging != view.charging:
            await self.log_event(headset_id, "charging", {"charging": hb.charging, "level": hb.battery})
        if hb.current_pkg != view.current_pkg:
            await self.log_event(headset_id, "app_change", {"from": view.current_pkg, "to": hb.current_pkg})
        if hb.adb != view.adb:
            await self.log_event(headset_id, "adb_status", {"from": view.adb, "to": hb.adb})
        if hb.guard_pkg != view.guard_pkg:
            await self.log_event(headset_id, "guard", {"pkg": hb.guard_pkg})

        view.battery = hb.battery
        view.charging = hb.charging
        view.temp = hb.temp
        view.current_pkg = hb.current_pkg
        view.adb = hb.adb
        view.sleep_disabled = hb.sleep_disabled
        view.guard_pkg = hb.guard_pkg
        view.screen_on = hb.screen_on
        if hb.controllers is not None:
            before = {c.side: c.battery for c in view.controllers}
            for c in hb.controllers:
                if c.connected and c.battery is not None and before.get(c.side) != c.battery:
                    await self.log_event(headset_id, "controller_battery", {"side": c.side, "level": c.battery})
            view.controllers = sorted(hb.controllers, key=lambda c: c.side)
        view.last_seen = utcnow()
        # на каждом heartbeat, а не только при смене: после переподключения игра может идти дальше
        await self._sessions.on_app(headset_id, hb.current_pkg)
        await self._publish(headset_id)

    async def disconnect(self, headset_id: str, ws: WebSocket, reason: str) -> None:
        # Если шлем уже переподключился, старое соединение не должно делать его офлайн
        if self._sockets.get(headset_id) is not ws:
            return
        del self._sockets[headset_id]
        view = self._views[headset_id]
        view.online = False
        await self._sessions.end(headset_id, "offline")
        # Спящий шлем пропадает из сети штатно: в статистике обрывов это не должно считаться
        if view.screen_on is False and reason in ("timeout", "dropped"):
            reason = "asleep"
        await self.log_event(headset_id, "disconnect", {"reason": reason, "screenOn": view.screen_on})
        await self._publish(headset_id)

    async def sweep(self) -> None:
        """Отключить шлемы, от которых давно ничего не приходило (соединение «повисло»)."""
        limit = utcnow() - timedelta(seconds=self._settings.offline_after_s)
        for headset_id, ws in list(self._sockets.items()):
            last_seen = self._views[headset_id].last_seen
            if last_seen is not None and last_seen < limit:
                log.info("headset %s timed out", headset_id)
                await self.disconnect(headset_id, ws, "timeout")
                await _close_quietly(ws, CLOSE_TIMEOUT)

    async def persist(self) -> None:
        if not self._dirty:
            return
        dirty, self._dirty = self._dirty, set()
        async with self._sf() as s:
            for headset_id in dirty:
                view = self._views.get(headset_id)
                if view is None:
                    continue
                await s.merge(
                    HeadsetState(
                        headset_id=headset_id,
                        online=view.online,
                        battery=view.battery,
                        charging=view.charging,
                        temp=view.temp,
                        current_pkg=view.current_pkg,
                        adb=view.adb,
                        sleep_disabled=view.sleep_disabled,
                        agent_version=view.agent_version,
                        last_seen=view.last_seen,
                        guard_pkg=view.guard_pkg,
                    )
                )
            await s.commit()

    async def shutdown(self) -> None:
        for headset_id, ws in list(self._sockets.items()):
            await self.disconnect(headset_id, ws, "server_shutdown")
        await self.persist()

    async def log_event(self, headset_id: str, type_: str, payload: dict[str, Any]) -> None:
        async with self._sf() as s:
            s.add(Event(headset_id=headset_id, type=type_, payload=payload))
            await s.commit()

    async def _publish(self, headset_id: str) -> None:
        self._dirty.add(headset_id)
        await self._hub.broadcast(LiveHeadset(headset=self._views[headset_id].model_copy()))


def _as_utc(value: datetime | None) -> datetime | None:
    # SQLite не хранит часовой пояс: всё, что мы пишем, — UTC
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


async def _close_quietly(ws: WebSocket, code: int) -> None:
    try:
        await ws.close(code=code)
    except Exception:
        pass
