# server: Python, FastAPI, SQLite

## Run

```bash
cd server
export HM_ADMIN_TOKEN=dev-admin   # required, the server does not start without it
uv run headset-server             # http://localhost:8000, migrations run by themselves
```

Settings: `HM_*` variables or a `.env` file (see `src/headset_server/config.py`):
`HM_DATABASE_URL` (default `sqlite+aiosqlite:///./headsets.db`), `HM_PORT`, `HM_OFFLINE_AFTER_S` and others.

Run as **one process** (no `--workers`): online headsets and their connections live in memory.

## Fake headsets (dashboard work without a headset)

```bash
HM_ADMIN_TOKEN=dev-admin uv run python tools/fake_agent.py --count 3
```

## API

| What | Where |
|---|---|
| Health | `GET /health` |
| Headset list | `GET /api/headsets` |
| Register a headset (provision.sh) | `POST /api/headsets`, header `Authorization: Bearer $HM_ADMIN_TOKEN` |
| Agent on the headset | `WS /agent` |
| Dashboard live updates | `WS /live`: first `{"type":"snapshot","headsets":[...]}`, then `{"type":"headset","headset":{...}}` |
| Docs (Swagger) | `GET /docs` |

Protocol: `src/headset_server/protocol.py` (source of truth). Schemas for the dashboard:
`uv run python tools/export_schema.py` → `schema/openapi.json`, `schema/live.json`, `schema/rest.json`.

## Tests and migrations

```bash
uv run pytest
uv run alembic revision --autogenerate -m "what changed"   # after editing db.py
```
