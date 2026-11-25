# ADR-0018: No protection without our server

- **Status:** Accepted
- **Date:** 2026-11-04
- **Related:** ADR-0017

## Context

A short Wi-Fi drop must not remove protection, so there is a delay of 30 s. Why protection must end without the server: not recorded.

## Decision

Remove protection effects after 30 s without connection to the server. Keep the setting and apply it again when the connection is back.

## Consequences

- After the agent starts, protection does not work until the first connection.
- **Checked by:** no automatic check. The agent has no automatic tests: it is checked by hand on headset 203. Last check: agent 0.9.0 (still on after 12 s, removed after 40 s).

## Alternatives considered

Not recorded.
