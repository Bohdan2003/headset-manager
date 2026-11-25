# ADR-0008: No helper process

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related:** ADR-0005

## Context

C commands need the rights of `shell`. A helper process on the headset could keep them. Why we did not want it: not recorded.

## Decision

Send prepared commands from the agent straight to `adbd`. Reconnect before a command if the connection is gone.

## Consequences

- Login to adbd takes about 2 s, so C commands are slower after a lost connection.
- **Checked by:** no automatic check. It is an architecture choice.

## Alternatives considered

A Shizuku-style helper — postponed: only if connection drops become a problem.
