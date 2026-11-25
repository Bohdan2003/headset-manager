# ADR-0017: Protection only on a running game

- **Status:** Accepted
- **Date:** 2026-11-04
- **Related:** ADR-0016, ADR-0018

## Context

Return to the game, no sleep, the power button lock and wake after a short press are needed at the same time.

## Decision

Give the dashboard one Protection switch that joins all four. Turn it on only when a game is running.

## Consequences

- Protection has no separate sleep control on the dashboard.
- **Checked by:** `test_guard_params` checks the command params. The behavior on the headset is checked by hand on 203.

## Alternatives considered

Not recorded.
