# ADR-0019: No wake from the dashboard

- **Status:** Accepted
- **Date:** 2026-11-04
- **Related:** ADR-0020

## Context

A sleeping headset is reachable for only about 2 minutes.

## Decision

Do not offer wake on the dashboard. Wake the headset with the button or by putting it on.

## Consequences

- The agent may wake the headset by itself after a short power press under protection.
- **Checked by:** no automatic check. `reviewer` looks for it in the diff. There is no `wake` in `CommandName`.

## Alternatives considered

Not recorded.
