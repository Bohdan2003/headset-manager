import asyncio
import logging

import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from .auth import COOKIE
from .db import Headset, utcnow
from .protocol import Ack, AgentEvent, Apps, Heartbeat, Hello, LiveSnapshot, UpdateProgress, Welcome, agent_message
from .registry import Registry
from .security import token_matches

log = logging.getLogger(__name__)
router = APIRouter()

CLOSE_BAD_HELLO = 4400
CLOSE_UNAUTHORIZED = 4401


@router.websocket("/agent")
async def agent_socket(ws: WebSocket) -> None:
    """
    Соединение с агентом на шлеме. Первое сообщение — hello с headsetId и токеном,
    дальше heartbeat раз в heartbeat_interval_s и события.
    """
    state = ws.app.state
    registry: Registry = state.registry
    await ws.accept()

    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=state.settings.hello_timeout_s)
        hello = agent_message.validate_json(raw)
    except (asyncio.TimeoutError, ValidationError, WebSocketDisconnect):
        await _close(ws, CLOSE_BAD_HELLO)
        return
    if not isinstance(hello, Hello):
        await _close(ws, CLOSE_BAD_HELLO)
        return

    async with state.session_factory() as s:
        headset = await s.get(Headset, hello.headset_id)
    if headset is None or not token_matches(hello.token, headset.token_hash):
        log.warning("agent rejected: headset_id=%s", hello.headset_id)
        await _close(ws, CLOSE_UNAUTHORIZED)
        return

    await registry.connect(headset.id, ws, hello)
    await ws.send_text(
        Welcome(server_time=utcnow(), heartbeat_interval_s=state.settings.heartbeat_interval_s).to_json()
    )

    reason = "closed"
    try:
        while True:
            raw = await ws.receive_text()
            registry.touch(headset.id)
            try:
                msg = agent_message.validate_json(raw)
            except ValidationError as e:
                # Битое сообщение не повод рвать связь со шлемом
                log.warning("bad message from %s: %s", headset.id, e.errors()[:1])
                continue
            match msg:
                case Heartbeat():
                    await registry.heartbeat(headset.id, msg)
                case AgentEvent(kind="update_progress"):  # не в журнал: это десятки строк за секунду
                    try:
                        await registry.set_update(headset.id, UpdateProgress.model_validate(msg.payload))
                    except ValidationError:
                        log.warning("bad update progress from %s", headset.id)
                case AgentEvent():
                    await registry.log_event(headset.id, msg.kind, msg.payload)
                    if msg.kind == "update_failed":
                        reason = str(msg.payload.get("reason", ""))[:300]
                        await registry.set_update(headset.id, UpdateProgress(stage="failed", reason=reason))
                    if msg.kind == "guard_relaunch":
                        await state.sessions.on_guard_return(headset.id)
                    elif msg.kind == "power_restart":
                        # игру запустили заново — это новая сессия
                        await state.sessions.end(headset.id, "power_button")
                case Apps():
                    await registry.set_apps(headset.id, msg.apps)
                case Ack():
                    await state.commands.on_ack(headset.id, msg)
                case Hello():
                    pass
    except WebSocketDisconnect as e:
        # 1000/1001 — агент закрыл соединение сам (перезагрузка, выключение); остальное — обрыв
        reason = "closed" if e.code in (1000, 1001) else "dropped"
    except Exception:
        log.exception("agent connection %s failed", headset.id)
        reason = "error"
    finally:
        # Задачу обработчика могут отменить (обрыв, остановка сервера) — очистка должна
        # дойти до конца, иначе шлем «повиснет» онлайн, а сессия игры останется открытой
        with anyio.CancelScope(shield=True):
            await registry.disconnect(headset.id, ws, reason)


@router.websocket("/live")
async def live_socket(ws: WebSocket) -> None:
    """Соединение с дашбордом: сначала весь список шлемов, потом изменения по одному."""
    state = ws.app.state
    await ws.accept()
    if state.settings.auth_enabled and not state.auth.session_valid(ws.cookies.get(COOKIE)):
        await _close(ws, CLOSE_UNAUTHORIZED)
        return
    snapshot = LiveSnapshot(headsets=state.registry.snapshot(), commands=state.commands.last_per_headset())
    await ws.send_text(snapshot.to_json())
    state.hub.add(ws)
    try:
        while True:
            await ws.receive_text()  # дашборд ничего не шлёт; ждём закрытия
    except WebSocketDisconnect:
        pass
    finally:
        state.hub.remove(ws)


async def _close(ws: WebSocket, code: int) -> None:
    try:
        await ws.close(code=code)
    except Exception:
        pass
