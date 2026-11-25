# ADR-0016: Sleep is disabled only under protection

- **Status:** Accepted
- **Date:** 2026-11-04
- **Related:** ADR-0017

## Context

Before agent 0.7.0 sleep was disabled on every agent start. In 0.9.0 we tried turning protection on in advance.

## Decision

Disable sleep only while protection is on.

## Consequences

- Without protection a headset that was taken off goes to sleep and goes offline.
- **Checked by:** no automatic check. The agent has no automatic tests: it is checked by hand on headset 203.

## Alternatives considered

Protection turned on in advance (agent 0.9.0) — tried and removed (user's decision).
