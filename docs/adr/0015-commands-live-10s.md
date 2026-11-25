# ADR-0015: Commands live about 10 seconds

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related:** ADR-0020

## Context

A command for an offline headset must not run unexpectedly later.

## Decision

Give every command a short life (`ttl_s`, 10 s by default). Do not queue commands for offline headsets. (`update_agent` uses 60 s: its `ack` comes after the download.)

## Consequences

- The operator must repeat a command that failed.
- **Checked by:** `test_offline_headset_fails_immediately`, `test_no_ack_becomes_timeout`.

## Alternatives considered

Not recorded.
