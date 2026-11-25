# T-002: Controller battery wear statistics

- **Role:** server-dev, then dashboard-dev
- **Status:** backlog
- **Priority:** 1
- **Output:** statistics on the Statistics tab

## Context

`controller_battery` events are already written. The agent already sends everything. See `docs/architecture/features/controllers.md`.

## What to do

1. Agree with the user which numbers to show.
2. Count them on the server, with tests.
3. Show them on the Statistics tab.

## Acceptance criteria

- [ ] Server tests cover the new numbers and pass.
- [ ] `npm run lint` and `npm run build` pass.
- [ ] The agent is not changed.
- [ ] `features/controllers.md` and `features/stats.md` are updated.

## Log

- 2026-11-25: task created from `docs/status.md`.
