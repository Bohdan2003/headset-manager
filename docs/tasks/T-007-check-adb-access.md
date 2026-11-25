# T-007: Check local ADB access on the headset

- **Role:** main session
- **Status:** review
- **Priority:** before the pilot
- **Output:** rows in `docs/research/quest-checks.md`

## Context

Three things are written but not checked on a headset. See `docs/architecture/features/adb-access.md`.

## What to do

1. `request_access` (agent 0.10.3).
2. `adb_allowed_connection_time = 0` keeps the key for 8+ days without connections.
3. The "Allow" dialog when the headset moves to another access point.

## Acceptance criteria

- [ ] Each of the three has a row with the result.
- [ ] The rows are removed from "Not checked yet".

## Log

- 2026-11-25: task created from `docs/status.md`.
