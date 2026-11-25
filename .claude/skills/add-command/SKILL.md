---
name: add-command
description: Add a new command (or change one) that goes from the dashboard through the server to the agent on the headset. Use when a task needs a new cmd value or new command params.
---

# Add a command

A command touches every part of the system. Do the steps in this order. Steps 1–4 can go to `server-dev`, step 5 to `dashboard-dev`, step 6 to `agent-dev`, step 8 to `reviewer`.

First decide with the user:
- Name (`snake_case`) and params.
- Level: **B** (normal app permissions) or **C** (needs local ADB, else `no_adb`).
- The exact prepared shell command for C. Never a shell string from the server.
- Is it allowed for a sleeping headset? (Default: no, the server answers `asleep`.)

## Steps

1. **Protocol.** `server/src/headset_server/protocol.py`: add the name to `CommandName`. Update the comment that lists B and C commands.
2. **Server check.** Validate params for this command where the other commands are checked (`api.py` / `commands.py`). Package names: `PACKAGE_RE`. If the command ends a session (like `close_game`), handle it in `sessions.py`.
3. **Tests.** Add tests in `server/tests/test_commands.py`: good params, bad params (`bad_params`), offline, asleep. Run `uv run pytest`.
4. **Schemas.** `cd server && uv run python tools/export_schema.py`.
5. **Dashboard.** `cd dashboard && npm run gen:types`. Add the button in `src/components/ActionBar.tsx`, the label in `src/lib/format.ts`. English text. Confirm step for dangerous commands. For C: "available on N of M". `npm run lint && npm run build`.
6. **Agent.** `agent/.../Commands.kt`: map the name to the prepared action, send `ack` with the right `reason`. C commands run in the C thread and answer `no_adb` without ADB. Raise `versionName` and `versionCode`. `JAVA_HOME=/opt/homebrew/opt/openjdk@17 ./gradlew assembleDebug`.
7. **Docs (main session).** Add a row to the command table in `docs/architecture/protocol.md`. Update the feature doc, `docs/tasks/BOARD.md` with the task log, and `docs/progress/<today>.md`.
8. **Review.** Run the `reviewer` role.
9. **Headset test (main session only).** Write a short test plan for 203. Ask the user "yes" before installing and before each state-changing step. Never 207. Write results in `docs/research/quest-checks.md`.
