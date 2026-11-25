# ADR-0009: "Always allow on this network", not "Allow"

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related:** ADR-0005, T-007, T-013

## Context

"Allow" works once: after the first Wi-Fi drop the dialog comes back. "Always allow" works until the next reboot (checked 01.11).

## Decision

After every power on, the operator taps "Always allow on this network".

## Consequences

- Somebody must put on the headset after every reboot.
- Without it level C does not work, level B does.
- **Checked by:** no automatic check. It is a step for the operator. The dashboard shows `waiting_confirmation`.

## Alternatives considered

"Allow" — rejected: it does not survive a Wi-Fi drop.
