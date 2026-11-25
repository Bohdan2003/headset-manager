# T-011: Drops of sleeping headsets on charge

- **Role:** server-dev
- **Status:** backlog
- **Priority:** low
- **Output:** correct drop numbers

## Context

On charge, a sleeping headset appears and disappears from the network about once a minute. Drops in statistics are higher because of this. See `docs/architecture/features/power.md`.

## What to do

1. Find which drops are counted wrongly.
2. Fix the counting, with a test.

## Acceptance criteria

- [ ] A test reproduces the case and passes.
- [ ] `features/stats.md` describes the rule.

## Log

- 2026-11-25: task created from `docs/status.md`.
