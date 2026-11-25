# T-005: Check the Setup tab on a real headset

- **Role:** main session and the user
- **Status:** review
- **Priority:** before the pilot
- **Output:** rows in `docs/research/quest-checks.md`

## Context

Install, Update and Remove are tested only with a fake adb.

## What to do

1. Agree with the user on the headset. Never 207.
2. Check Install and Update after "yes".
3. Remove uninstalls the agent: only the user presses this button, Claude never uninstalls apps.

## Acceptance criteria

- [ ] Install, Update and Remove each have a row with the result.
- [ ] After Remove, power button and sleep settings are back to factory values.

## Log

- 2026-11-25: task created from `docs/status.md`.
