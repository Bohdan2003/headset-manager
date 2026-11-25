# ADR-0007: No ADB keys on the server

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related:** ADR-0004

## Context

A copy of the key on the server helps only if the agent lost its copy but the headset still trusts the key. That is rare. If the headset forgot the key (this happened on 31.10), the copy is useless.

## Decision

Store no ADB keys on the server.

## Consequences

- Any key loss = set up the headset again by cable.
- **Checked by:** no automatic check. `reviewer` looks for it in the diff.

## Alternatives considered

A copy of every key on the server — rejected, see Context.
