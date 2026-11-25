# T-008: Decide where to keep the agent signing key

- **Role:** user decides, main session writes the ADR
- **Status:** blocked
- **Priority:** before the pilot
- **Blocked by:** the user postponed it
- **Output:** ADR-0024 is Accepted

## Context

The agent is signed with the debug key on one Mac. If it is lost, installed agents can't be updated.

## What to do

1. Compare the options.
2. The user decides.
3. Fill ADR-0024.

## Acceptance criteria

- [ ] ADR-0024 has a decision, consequences and alternatives.
- [ ] No key is in the repository, logs or chat.

## Log

- 2026-11-25: task created from `docs/status.md`.
