# T-003: Faster wake after a short power press

- **Role:** agent-dev
- **Status:** backlog
- **Priority:** 2 (optional)
- **Output:** a new agent version

## Context

Wake takes about 2.5 s: almost all of it is the login to adbd. Idea: a wake lock that turns the screen on, about 0.5 s.

## What to do

1. Try the wake lock in the agent.
2. Measure on 203 (main session, after "yes").

## Acceptance criteria

- [ ] `./gradlew assembleDebug` passes.
- [ ] The measured time is in `docs/research/quest-checks.md`.
- [ ] If the idea does not work, the reason is written there too.

## Log

- 2026-11-25: task created from `docs/status.md`.
