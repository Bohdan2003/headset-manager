import logging

from fastapi import WebSocket

from .protocol import ProtocolModel

log = logging.getLogger(__name__)


class LiveHub:
    """Открытые соединения дашборда (/live). Рассылает им изменения состояния шлемов."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, message: ProtocolModel) -> None:
        data = message.to_json()
        for ws in list(self._clients):
            try:
                await ws.send_text(data)
            except Exception:
                log.info("live client dropped")
                self._clients.discard(ws)
