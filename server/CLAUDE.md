# server: Python, FastAPI, SQLite

How to run, API and tests: `README.md` in this folder.

## Stack

FastAPI (REST `/api`, WebSocket `/agent` for agents and `/live` for the dashboard), uvicorn, Pydantic v2, SQLAlchemy 2.0 async + `aiosqlite`, Alembic, `uv`, pytest + `httpx`.

## Rules

- **One uvicorn process**, never `--workers N`. Online headsets and open WebSockets live in memory.
- `protocol.py` is the source of truth. After changing it: `uv run python tools/export_schema.py`, then `cd ../dashboard && npm run gen:types`. CI checks that the types match.
- The server never runs ADB on headsets (only `setup_tools.py` uses adb, for setup and updates by cable on the server computer). It stores no ADB keys.
- Check command params per command. A package must match `PACKAGE_RE` (`^[a-zA-Z0-9_.]+$`).
- `update_agent` is accepted only from `POST /api/setup/update-wifi`. `/api/commands` returns 403 for it.
- After changing `db.py`: `uv run alembic revision --autogenerate -m "..."`. Never delete the database: it holds headset tokens.
- Cleanup on WebSocket close (`registry.disconnect`) runs in `anyio.CancelScope(shield=True)`. Otherwise it can be cancelled together with the handler task.
- Every behavior change needs a test. Run `uv run pytest` before you say "done".

## Modules (`src/headset_server/`)

| File | What |
|---|---|
| `protocol.py` | All messages (discriminated union by `type`) |
| `ws.py` | `WS /agent`: token check, hello, heartbeat. Offline = no heartbeat for 15 s or socket closed |
| `registry.py` | Headset state in memory + snapshots in the database |
| `commands.py` | `id`, status `sent → acked/failed/timeout`, TTL ~10 s, `offline` / `asleep` at once |
| `sessions.py`, `stats.py` | Sessions and statistics, see `docs/architecture/features/stats.md` |
| `live.py` | Sends changes to the dashboard |
| `auth.py` | Dashboard password, see `docs/architecture/features/auth.md` |
| `setup_tools.py` | Setup tab: install, update, remove. Repeats `scripts/provision.sh` |
| `api.py`, `db.py`, `config.py`, `paths.py`, `security.py`, `desktop.py` | REST, tables, settings (`HM_*`), data paths, tokens, Arena window |

Protocol and tables: `docs/architecture/protocol.md`.

## Testing without a headset

`HM_ADMIN_TOKEN=dev-admin uv run python tools/fake_agent.py --count 3`
