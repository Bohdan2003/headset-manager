"""
Выгружает схемы протокола для дашборда:
  schema/openapi.json   — REST API (из FastAPI)
  schema/live.json      — сообщения WebSocket /live (сервер → дашборд)
  schema/rest.json      — тела запросов и ответов REST, которые использует дашборд

    uv run python tools/export_schema.py

Из них дашборд генерирует TypeScript-типы, чтобы не разойтись с сервером.
"""

import json
from pathlib import Path

from pydantic import TypeAdapter

from headset_server import create_app
from headset_server.config import Settings
from headset_server.protocol import AuthStatus, CommandCreate, CommandView, LiveMessage, SetupInfo, SetupRequest, Stats, WifiUpdateRequest

OUT = Path(__file__).resolve().parent.parent / "schema"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    app = create_app(Settings(admin_token="schema-export"))
    (OUT / "openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    live = TypeAdapter(LiveMessage).json_schema(by_alias=True, mode="serialization")
    (OUT / "live.json").write_text(json.dumps(live, ensure_ascii=False, indent=2), encoding="utf-8")
    # json2ts берёт типы из корня схемы, поэтому собираем нужные модели в одно объединение
    rest = TypeAdapter(AuthStatus | CommandCreate | list[CommandView] | Stats | SetupInfo | SetupRequest | WifiUpdateRequest).json_schema(by_alias=True, mode="serialization")
    rest["title"] = "Rest"
    (OUT / "rest.json").write_text(json.dumps(rest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written to {OUT}")


if __name__ == "__main__":
    main()
