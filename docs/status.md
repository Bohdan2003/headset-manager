# Status

Read this at the start of a task. Update it at the end: move items, add the date.
Last update: 22.11.2026. Agent in code: 0.11.4 (versionCode 22). Headsets run 0.11.3 until updated.

## How to run

- Program: `dist/Arena.app` → http://localhost:8000. The real headsets are in the program's database.
- Development: `./scripts/start.sh`. It has its own database `server/headsets.db`.
- The agent on the headsets already points to the program's server.
- After every headset power on: "Always allow on this network" in the headset. Without it close game and reboot do not work, the rest works.
- The test app `com.arena.adbprobe` on the headset is disabled (`pm disable-user`), not removed.

## Done and checked on a real headset

- Server, protocol, registry, `/live`, dashboard list and summary tiles.
- B commands: launch, protection (return to game, sleep, power button), our menu.
- C commands: close game, restart game, reboot, sleep, power off.
- Agent starts after reboot by itself, comes back after Wi-Fi drops.
- Controller battery in heartbeat and on the dashboard.
- Statistics: sessions, games, headset health (drops, charge interruptions, battery life).
- Agent update over Wi-Fi (203: 0.11.2 → 0.11.3 in 6 s).
- Dashboard login with one password.
- CI on GitHub: tests, lint, type check, Mac and Windows builds pass (07.11, `994529d`).

## Done, not checked on a real device

- Agent 0.11.4 (bugs from the Windows test, 22.11):
  - charging: the card said "not charging" while power was connected. Now the agent also sends `plugged`, and the card shows "plugged in, not charging". Cause (likely, not confirmed on the device): a weak power source gives Android status `NOT_CHARGING`.
  - close game after "launch A, launch B" gave an error on the card. Now "Close game" closes every running game in one adbd session. Cause (likely, the error text was not seen): the agent closed only the game it thought was in front, and that value can be stale.
  - To check on 203: plug into a PC USB port → "plugged in, not charging"; launch A, launch B, Close game → our menu, `pidof` empty for both, card green.
- Install, Update and Remove from the Setup tab (only tests with a fake adb).
- `Arena.exe` on a real Windows computer. The adb key swap on Windows matters most here.
- `request_access` (agent 0.10.3).
- `adb_allowed_connection_time = 0` keeps the key for 8+ days.
- The "Allow" dialog when the headset moves to another access point.
- The lost key on 31.10: reason unknown, watch in the pilot.

## Next (user's priority)

1. Controller battery wear statistics (`controller_battery` events are already written). Server + dashboard.
2. Faster wake after a short power press (2.5 s → ~0.5 s, wake lock that turns the screen on). Optional.
3. At the very end: setup on a second headset, pilot with 2–3 headsets at the arena, log every drop, reconnect and key loss.

## Postponed or small

- Where to keep the agent signing key (postponed by the user, decide before the pilot).
- One implementation of setup: `provision.sh` and `setup_tools.py` repeat the same steps.
- Raise GitHub Actions versions (Node.js 20 warning, not blocking yet).
- Drops in statistics are higher for sleeping headsets on charge.
- Ideas: poll windows on a timer to tap "Allow"; report the "Always allow" bug to Meta.

## Risk to watch

After a Meta firmware update run `docs/firmware-checklist.md` first. Starting screens from the background may get blocked (`BAL hardening`).

## History

- 31.10: `adb tcpip` lost after reboot → no ADB on the server. A key disappeared from `adb_keys`.
- 01.11: B/C architecture, system design, first vertical slice, B and C commands, statistics, power button (agents 0.1.0–0.6.0).
- 04.11: protection as one switch, sleep/power off from the dashboard, Arena program, English UI, request access, headset rename, charging (agents 0.7.0–0.10.3).
- 07.11: agent update over Wi-Fi (0.11.x), sleeping headset, headset health statistics, dashboard login, CI/CD, first push.
- 22.11: CLAUDE.md split into `docs/`, per-part `CLAUDE.md`, roles, skills and a safety hook. Everything in English from now on.
