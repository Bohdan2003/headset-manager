# T-006: Check `Arena.exe` on a real Windows computer

- **Role:** user
- **Status:** review
- **Priority:** before the pilot
- **Output:** rows in `docs/research/quest-checks.md`

## Context

The program builds in CI, but setup from it was not checked on a real Windows computer. The adb key swap matters most there (`docs/architecture/features/provisioning.md`).

## What to do

1. Start `Arena.exe`, open the dashboard.
2. Set up a headset by cable (not 207).
3. Check the computer's adb key after setup and after a crash.

## Acceptance criteria

- [ ] The program starts and the dashboard opens.
- [ ] The headset gets its own key, not the computer's key.
- [ ] The computer's key is back after setup.

## Log

- 2026-11-25: task created from `docs/status.md`.
