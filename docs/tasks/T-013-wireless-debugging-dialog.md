# T-013: Avoid the dialog on every boot

- **Role:** agent-dev, user
- **Status:** backlog
- **Priority:** idea
- **Output:** a result in `docs/research/quest-checks.md`

## Context

Quest does not remember "Always allow on this network" after a reboot. It looks like a Meta bug. The Accessibility service gets no events from this dialog.

## What to do

1. Idea 1: poll windows on a timer to tap "Allow" (code is in `spike/adb-probe`).
2. Idea 2: the user reports the bug to Meta.

## Acceptance criteria

- [ ] The result of idea 1 is written.
- [ ] The bug is reported, or it is written that we do not report it.

## Log

- 2026-11-25: task created from `docs/status.md`.
