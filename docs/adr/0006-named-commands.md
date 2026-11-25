# ADR-0006: The server sends meanings, not shell

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related:** ADR-0005

## Context

A shell command from the network would give the sender `shell` rights on the headset.

## Decision

Send only named commands (`launch`, `close_game`, `reboot`, ...). The agent maps each one to a prepared shell command. A package name must match `^[a-zA-Z0-9_.]+$` before it goes into a shell command.

## Consequences

- A new command needs a change in the server, the dashboard and the agent (skill `/add-command`).
- **Checked by:** `test_bad_params_rejected_before_reaching_agent` on the server. The mapping and the package check in the agent (`PACKAGE_RE` in `Commands.kt`) have no automatic test.

## Alternatives considered

Any shell command from the server — rejected, must stay impossible.
