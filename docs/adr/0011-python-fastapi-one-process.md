# ADR-0011: Python, FastAPI and SQLite in one process

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related:** ADR-0012

## Context

The server holds open WebSockets and the list of online headsets.

## Decision

Use Python, FastAPI and SQLite. Run exactly one uvicorn process and keep online headsets in its memory.

## Consequences

- `--workers N` breaks the system.
- PostgreSQL later, only if needed.
- **Checked by:** no automatic check. `workers=1` is written in `server/src/headset_server/__init__.py` and `desktop.py`; `reviewer` looks at the diff.

## Alternatives considered

Not recorded.
