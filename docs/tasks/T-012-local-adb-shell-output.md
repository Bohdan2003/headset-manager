# T-012: Empty or shifted output of `LocalAdb.shell()`

- **Role:** agent-dev
- **Status:** backlog
- **Priority:** low
- **Output:** a yes/no answer, and a fix if needed

## Context

`LocalAdb.shell()` sometimes returned empty or shifted output in the spike app. It is not known if the agent still has this.

## What to do

1. Read the code and find the possible cause.
2. Give the main session a test plan for 203.

## Acceptance criteria

- [ ] It is written whether the agent has the problem.
- [ ] If it has: fixed, and `./gradlew assembleDebug` passes.

## Log

- 2026-11-25: task created from `docs/status.md`.
