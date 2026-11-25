# T-004: Set up a second headset and run a pilot

- **Role:** main session and the user
- **Status:** backlog
- **Priority:** 3 (at the very end)
- **Blocked by:** T-005, T-008
- **Output:** a pilot report in `docs/research/`

## Context

Setup was not fully checked on a second headset. On 31.10 a key disappeared from `adb_keys` within one hour, the reason is unknown.

## What to do

1. The user names the headsets. Claude never works with 207.
2. Set up a second headset.
3. Run a pilot with 2–3 headsets at the arena.
4. Log every drop, reconnect and key loss. Watch for the lost key.

## Acceptance criteria

- [ ] The second headset reaches `adb: ready`.
- [ ] Every drop, reconnect and key loss in the pilot is logged.
- [ ] The lost key: cause found, or "did not happen again" is written.

## Log

- 2026-11-25: task created from `docs/status.md`.
