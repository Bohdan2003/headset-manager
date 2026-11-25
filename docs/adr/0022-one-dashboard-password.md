# ADR-0022: One shared password for the dashboard

- **Status:** Accepted
- **Date:** 2026-11-07
- **Related:** `docs/architecture/features/auth.md`

## Context

The dashboard works in the local network. Why one shared password: not recorded.

## Decision

Protect the dashboard with one shared password.

## Consequences

- The server works over http, so the password is not encrypted on the way.
- **Checked by:** `server/tests/test_auth.py`.

## Alternatives considered

Not recorded.
