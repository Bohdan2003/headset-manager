# server — Python, FastAPI, SQLite

## Запуск

```bash
cd server
export HM_ADMIN_TOKEN=dev-admin   # обязателен, без него сервер не стартует
uv run headset-server             # http://localhost:8000, миграции применяются сами
```

Настройки — переменные `HM_*` или файл `.env` (см. `src/headset_server/config.py`):
`HM_DATABASE_URL` (по умолчанию `sqlite+aiosqlite:///./headsets.db`), `HM_PORT`, `HM_OFFLINE_AFTER_S` и др.

Запускать **одним процессом** (без `--workers`): онлайн-шлемы и их соединения живут в памяти.

## Эмулятор шлемов (для разработки дашборда без шлема)

```bash
HM_ADMIN_TOKEN=dev-admin uv run python tools/fake_agent.py --count 3
```

## API

| Что | Где |
|---|---|
| Здоровье | `GET /health` |
| Список шлемов | `GET /api/headsets` |
| Регистрация шлема (provision.sh) | `POST /api/headsets`, заголовок `Authorization: Bearer $HM_ADMIN_TOKEN` |
| Агент на шлеме | `WS /agent` |
| Дашборд, живые обновления | `WS /live`: сначала `{"type":"snapshot","headsets":[...]}`, потом `{"type":"headset","headset":{...}}` |
| Документация (Swagger) | `GET /docs` |

Протокол — `src/headset_server/protocol.py` (источник истины). Схемы для дашборда:
`uv run python tools/export_schema.py` → `schema/openapi.json`, `schema/live.json`.

## Тесты и миграции

```bash
uv run pytest
uv run alembic revision --autogenerate -m "что изменилось"   # после правки db.py
```
