import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from .db import CommandRow, utcnow
from .live import LiveHub
from .protocol import Ack, Command, CommandCreate, CommandView, LiveCommand
from .registry import Registry
from .sessions import Sessions

log = logging.getLogger(__name__)

# Запас сверх ttl: команда дошла до агента в последний момент и он успевает ответить
ACK_GRACE_S = 5


@dataclass
class _Pending:
    view: CommandView
    deadline: datetime


class Commands:
    """
    Команды шлемам: отправить агенту, дождаться ack, отметить результат.
    Шлему офлайн команда не ставится в очередь — она сразу failed/offline:
    иначе игра могла бы неожиданно запуститься, когда шлем вернётся через полчаса.
    """

    def __init__(
        self, session_factory: async_sessionmaker, registry: Registry, hub: LiveHub, sessions: Sessions
    ) -> None:
        self._sf = session_factory
        self._sessions = sessions
        self._registry = registry
        self._hub = hub
        self._pending: dict[str, _Pending] = {}
        self._last: dict[str, CommandView] = {}  # последняя команда каждому шлему

    def last_per_headset(self) -> list[CommandView]:
        return list(self._last.values())

    async def create(self, body: CommandCreate) -> list[CommandView]:
        result = []
        for headset_id in dict.fromkeys(body.headset_ids):  # без повторов, порядок сохраняем
            if not self._registry.exists(headset_id):
                continue
            view = CommandView(
                id=str(uuid.uuid4()),
                headset_id=headset_id,
                cmd=body.cmd,
                params=body.params,
                status="sent",
                created_at=utcnow(),
            )
            # Спящий шлем команду не выполнит, разбудить его с дашборда нельзя: отвечаем сразу, а не таймаутом
            asleep = self._registry.is_asleep(headset_id)
            sent = not asleep and await self._registry.send(
                headset_id, Command(id=view.id, cmd=body.cmd, params=body.params, ttl_s=body.ttl_s)
            )
            if sent:
                deadline = view.created_at + timedelta(seconds=body.ttl_s + ACK_GRACE_S)
                self._pending[view.id] = _Pending(view, deadline)
            else:
                view.status, view.reason = "failed", "asleep" if asleep else "offline"
            await self._save(view, new=True)
            result.append(view)
        return result

    async def on_ack(self, headset_id: str, ack: Ack) -> None:
        pending = self._pending.pop(ack.id, None)
        if pending is None or pending.view.headset_id != headset_id:
            log.info("ack for unknown command %s from %s", ack.id, headset_id)
            return
        view = pending.view
        view.status = "acked" if ack.ok else "failed"
        view.reason = None if ack.ok else (ack.reason or "failed")
        view.detail = ack.detail
        view.acked_at = utcnow()
        await self._save(view)
        reason = {"close_game": "closed", "show_menu": "menu", "restart_game": "restarted"}.get(view.cmd)
        if ack.ok and reason:
            await self._sessions.end(headset_id, reason)

    async def sweep(self) -> None:
        """Агент не ответил вовремя (команда потерялась, агент завис)."""
        now = utcnow()
        for command_id, pending in list(self._pending.items()):
            if pending.deadline < now:
                del self._pending[command_id]
                pending.view.status, pending.view.reason = "timeout", "timeout"
                await self._save(pending.view)

    async def _save(self, view: CommandView, new: bool = False) -> None:
        async with self._sf() as s:
            if new:
                s.add(
                    CommandRow(
                        id=view.id, headset_id=view.headset_id, cmd=view.cmd, params=view.params,
                        status=view.status, reason=view.reason, created_at=view.created_at,
                    )
                )
            else:
                row = await s.get(CommandRow, view.id)
                if row is not None:
                    row.status, row.reason, row.detail, row.acked_at = (
                        view.status, view.reason, view.detail, view.acked_at,
                    )
            await s.commit()
        last = self._last.get(view.headset_id)
        if last is None or last.id == view.id or last.created_at <= view.created_at:
            self._last[view.headset_id] = view
        await self._hub.broadcast(LiveCommand(command=view.model_copy()))
