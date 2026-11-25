# ADR-0023: `update_agent` only through the setup endpoint

- **Status:** Accepted
- **Date:** 2026-11-07
- **Related:** `docs/architecture/features/wifi-update.md`

## Context

`update_agent` installs a program on the headset. Setup endpoints work only from the server computer.

## Decision

Accept `update_agent` only from `POST /api/setup/update-wifi`. `/api/commands` answers 403.

## Consequences

- An agent update can be started only on the server computer.
- **Checked by:** `test_update_cannot_be_sent_as_ordinary_command`, `test_wifi_update_refused_from_the_network`.

## Alternatives considered

Not recorded.
