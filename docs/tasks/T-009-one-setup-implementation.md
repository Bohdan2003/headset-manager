# T-009: One implementation of setup

- **Role:** server-dev (`setup_tools.py`), main session (`scripts/`)
- **Status:** backlog
- **Priority:** low
- **Output:** one code path

## Context

`scripts/provision.sh` and `server/src/headset_server/setup_tools.py` repeat the same steps.

## What to do

1. Write an ADR: which one stays.
2. Make one call the other, or remove one.

## Acceptance criteria

- [ ] The steps exist in one place.
- [ ] `uv run pytest` passes.
- [ ] `features/provisioning.md` is updated.

## Log

- 2026-11-25: task created from `docs/status.md`.
