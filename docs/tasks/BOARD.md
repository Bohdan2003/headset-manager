# Task board

Read this at the start of a task. Update it at the end, together with the **Log** in the task file and `docs/progress/<today>.md`. The main session does this. Roles only report.

Statuses: `backlog` → `in-progress` → `review` → `done` | `blocked`

- `review` = written, but not checked yet (most often: not checked on a real headset).
- `done` only with the output of the checks: `uv run pytest` (server), `npm run lint` and `npm run build` (dashboard), `./gradlew assembleDebug` (agent, see `agent/CLAUDE.md` for `JAVA_HOME`). If the task changes headset behavior, also a row in `docs/research/quest-checks.md`.

## Now

- Agent in code: 0.11.4 (versionCode 22). Headsets run 0.11.3 until updated (T-001).
- The user's order: T-002, then T-003 (optional), then T-004 at the very end.

## Tasks

| ID | Task | Role | Priority | Status | Updated |
|---|---|---|---|---|---|
| [T-001](T-001-check-agent-0-11-4.md) | Check agent 0.11.4 on headset 203 | main session | high | review | 2026-11-25 |
| [T-002](T-002-controller-battery-wear.md) | Controller battery wear statistics | server-dev, then dashboard-dev | 1 | backlog | 2026-11-25 |
| [T-003](T-003-faster-wake.md) | Faster wake after a short power press | agent-dev | 2 (optional) | backlog | 2026-11-25 |
| [T-004](T-004-second-headset-and-pilot.md) | Set up a second headset and run a pilot | main session and the user | 3 (at the very end) | backlog | 2026-11-25 |
| [T-005](T-005-check-setup-tab.md) | Check the Setup tab on a real headset | main session and the user | before the pilot | review | 2026-11-25 |
| [T-006](T-006-check-arena-exe.md) | Check `Arena.exe` on a real Windows computer | user | before the pilot | review | 2026-11-25 |
| [T-007](T-007-check-adb-access.md) | Check local ADB access on the headset | main session | before the pilot | review | 2026-11-25 |
| [T-008](T-008-agent-signing-key.md) | Decide where to keep the agent signing key | user decides, main session writes the ADR | before the pilot | blocked | 2026-11-25 |
| [T-009](T-009-one-setup-implementation.md) | One implementation of setup | server-dev (`setup_tools.py`), main session (`scripts/`) | low | backlog | 2026-11-25 |
| [T-010](T-010-github-actions-versions.md) | Raise GitHub Actions versions | main session | low | backlog | 2026-11-25 |
| [T-011](T-011-drops-asleep-on-charge.md) | Drops of sleeping headsets on charge | server-dev | low | backlog | 2026-11-25 |
| [T-012](T-012-local-adb-shell-output.md) | Empty or shifted output of `LocalAdb.shell()` | agent-dev | low | backlog | 2026-11-25 |
| [T-013](T-013-wireless-debugging-dialog.md) | Avoid the dialog on every boot | agent-dev, user | idea | backlog | 2026-11-25 |

## New task

One file `T-NNN-kebab-case-title.md` with the next free number: Role, Status, Priority, Blocked by (if any), Output, Context, What to do, Acceptance criteria that can be checked, Log. Add its row here.
