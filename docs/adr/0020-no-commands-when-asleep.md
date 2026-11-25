# ADR-0020: No commands to a sleeping headset

- **Status:** Accepted
- **Date:** 2026-11-07
- **Related:** ADR-0015, ADR-0019

## Context

A command to a sleeping headset would wait for a timeout.

## Decision

Answer `failed / asleep` at once and do not send the command.

## Consequences

- On the dashboard the buttons are disabled if only sleeping headsets are selected.
- **Checked by:** `test_asleep_headset_refuses_commands_at_once`.

## Alternatives considered

Wait for a timeout — rejected.
