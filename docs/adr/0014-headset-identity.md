# ADR-0014: Headset identity: serial number, label and token

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related:** `docs/architecture/features/provisioning.md`

## Context

A headset must keep its history after a factory reset, and another device must not be able to pretend to be our headset.

## Decision

Identify a headset by serial number. Give it a label for people and a secret token for the connection.

## Consequences

- After a factory reset the headset is found by serial number and keeps its history.
- **Checked by:** `test_wrong_token_is_rejected`, `test_reprovision_same_serial_keeps_id_and_rotates_token`.

## Alternatives considered

Not recorded.
