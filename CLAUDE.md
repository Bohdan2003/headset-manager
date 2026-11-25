# Arena: Meta Quest headset manager

An internal tool to manage our Meta Quest headsets at a VR arena. Not for sale.
We write **our own implementation**. Do not suggest ready-made MDM tools (ManageXR, ArborXR and similar).

## Language

Everything is in English: chat replies, docs, code comments, commit messages and the UI.
Use simple English (level B1, a little B2): short sentences, common words, explain terms the first time.
Old Russian comments in the code: translate them when you edit that file, do not rewrite whole files just for this.

## The system in one picture

```
Arena computer (one program, one port, local network, no internet)
├─ server/     Python, FastAPI, SQLite. WS /agent for headsets, REST /api + WS /live for the dashboard
├─ dashboard/  React + Vite + TypeScript + Tailwind. FastAPI serves its build on "/"
└─ packaging/  Arena.app / Arena.exe: server + dashboard + adb + agent.apk in one program
                        │ WebSocket over Wi-Fi
agent/  Kotlin app on every headset
├─ B: normal app permissions: online, battery, current game, launch, our menu, protection, sleep
└─ C: local ADB (the agent logs in to adbd on 127.0.0.1 with its own key): close game, reboot, install, wake (only by the agent itself under protection)
```

## Key decisions (reasons in `docs/adr/`)

- Developer mode is always on. We can rely on ADB and `shell` rights, but only **inside the headset** (part C).
- We can't become Device Owner on Quest (only Meta partners). We can't block the Meta button, only notice the exit and bring the player back.
- The server never uses ADB on headsets and stores **no ADB keys**. If a key is lost, set up the headset again by cable.
- The server sends only named commands (`launch`, `close_game`, ...). The agent maps them to **prepared** shell commands. Any shell command from the server is impossible. A package name must match `^[a-zA-Z0-9_.]+$` before it goes into a shell command.
- B does not depend on C. Without ADB the headset stays online and the agent answers strong commands with `ack { ok: false, reason: "no_adb" }`.
- `server/src/headset_server/protocol.py` (Pydantic) is the source of truth for the protocol. Dashboard types are generated from it, the agent copies the same JSON.
- Run the server as **one uvicorn process** (no `--workers`): online headsets live in memory.

## Rules for working with headsets

A hook (`.claude/hooks/guard-bash.py`) catches the most common mistakes. It can't catch everything (it knows 207 only by serial), so follow the rules yourself.

- **Never touch headset 207 (`1WMHH868671295`):** no commands, installs, updates or checks. Test on 203 (`1WMHHA717K3282`).
- **Never run `am force-stop com.arena.agent`.** Android then turns off the agent's Accessibility service and does not start the agent again. The headset goes offline. (Happened on 01.11. Fix: `settings put secure enabled_accessibility_services com.arena.agent/com.arena.agent.WatcherService`.)
- Read-only commands (`devices`, `getprop`, `dumpsys`, `pm list`, `settings get`) are fine without asking.
- New permissions from `pm grant` work without a restart. To update the agent use `adb install -r`: the agent restarts by itself.
- Before any command that changes the headset (`reboot`, `force-stop`, launching games, `settings put`, `pm grant`, broadcasts, installs, key approval): say in one line what you will do and wait for "yes".
- Never do a factory reset, never uninstall apps, never revoke debugging permissions. (The operator may use Remove on the Setup tab. Claude may not.)
- Never print private keys in chat, logs or commits. Key files belong in `.gitignore`.
- Never approve the USB debugging dialog for an unknown key: a stranger's computer would get access.
- Only the main session works with headsets. Subagents do not run `adb` against a device.
- If something does not work on the headset, look for the current way for this Meta OS version before saying "impossible". Write every result into `docs/research/quest-checks.md`.

## Where to read more

Read a file when your task touches its topic. Do not load all of them.

| Topic | File |
|---|---|
| Short overview for people | `README.md` |
| Tasks, what is not checked, what is next | `docs/tasks/BOARD.md` (read at the start of a task, update at the end) |
| What happened, day by day | `docs/progress/` |
| Target architecture, rules between the parts | `docs/architecture/overview.md` |
| Why we decided something | `docs/adr/README.md` (index) |
| Messages, commands, statuses, database tables | `docs/architecture/protocol.md` |
| Checks on the real headset (works / does not work) | `docs/research/quest-checks.md` |
| After a Meta firmware update | `docs/research/firmware-checklist.md` |
| Local ADB (part C), "Always allow", key timer | `docs/architecture/features/adb-access.md` |
| Setting up a headset by cable, identity, Setup tab | `docs/architecture/features/provisioning.md` |
| Protection, power button, restart game | `docs/architecture/features/protection.md` |
| Sleep, power off, charging, sleeping headset | `docs/architecture/features/power.md` |
| Sessions and statistics | `docs/architecture/features/stats.md` |
| Controller battery | `docs/architecture/features/controllers.md` |
| Agent update over Wi-Fi | `docs/architecture/features/wifi-update.md` |
| Dashboard login | `docs/architecture/features/auth.md` |

Each part has its own `CLAUDE.md` (`server/`, `dashboard/`, `agent/`, `packaging/`). It loads when you work with files there.
Other folders: `scripts/` (`provision.sh` setup by cable, `start.sh` dev server), `spike/adb-probe/` (old test app for device checks, not the base of the agent).

## How we work

- Roles (subagents) are in `.claude/agents/`: `server-dev`, `dashboard-dev`, `agent-dev`, `reviewer`, `log-reader`.
- A task lives in `docs/tasks/T-NNN-*.md`, its row is in `BOARD.md`. `done` only with the output of the checks (list in `BOARD.md`).
- A decision = an ADR in `docs/adr/`. No accepted ADR means no decision.
- The main session owns `docs/`, `packaging/`, `scripts/` and `.claude/`. Roles report what to change there.
- Repeated procedures are skills in `.claude/skills/`: `/add-command`, `/update-agent-wifi`, `/device-check`, `/release`. Only `/add-command` can be started by Claude, the user types the others.
- A change to the protocol goes in this order: server → `export_schema` + `npm run gen:types` → dashboard and agent.
- Repository: https://github.com/Bohdan2003/headset-manager (private, branch `main`). Commit and push only when the user asks.
- Long project docs for people (diagrams, how it all works): https://claude.ai/artifact/RPWd7KQq72MycnYtQAEqJn
