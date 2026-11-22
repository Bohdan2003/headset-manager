# Decisions

Each decision has a date and a reason. If you want to change one, first read why it was made.

## Product

**Own implementation, no MDM.** We do not use ManageXR, ArborXR and similar tools. Do not suggest them.

**No Device Owner.** On Quest only Meta partners (HMS) can become Device Owner. So we can't block the Meta button. We can only notice that the player left and bring them back into the game.

**No statistics per player.** The headset does not know who is wearing it. Later we may link a session to a booking by hand.

## Headset control

**The server does not control headsets over ADB (31.10).** `adb tcpip` is lost after a headset reboot, and only a cable brings it back (tested 31.10). So no ADB on the server and no `@devicefarmer/adbkit`.

**Two levels on the headset: B and C (01.11).**
- B: normal app permissions, given once by cable. This is the base of the product: online, battery, current game, launching games, our menu, return to the game, sleep control.
- C: local ADB. The agent logs in to `adbd` on the headset with its own key. Needed only for strong commands: close game (`force-stop`), reboot, wake, power off, install.
- B never depends on C or on the key. Without C the agent answers `ack { ok: false, reason: "no_adb" }`.

**The server sends meanings, not shell (01.11).** Commands are `launch`, `close_game`, `reboot`... The agent maps them to prepared shell commands. A package name must match `^[a-zA-Z0-9_.]+$`.

**No ADB keys on the server (01.11).** A copy on the server helps only if the agent lost its copy but the headset still trusts the key. That is rare. If the headset forgot the key (this happened on 31.10), the copy is useless. Any key loss = set up again by cable.

**No helper process (01.11).** The agent sends prepared commands straight to `adbd` and reconnects before a command if the connection is gone. A Shizuku-style helper only if connection drops become a problem.

**"Always allow on this network", not "Allow" (01.11).** "Allow" works once: after the first Wi-Fi drop the dialog comes back. "Always allow" works until the next reboot.

**Never approve the USB debugging dialog with an unknown key.** A stranger's computer would get access to the headset.

## Server and dashboard

**Python + FastAPI + SQLite, one process (01.11).** Online headsets and open WebSockets live in the memory of one process. PostgreSQL later, only if needed.

**React + Vite, not Next.js (01.11).** We don't need SSR or API routes. FastAPI serves the built dashboard: one process, one port, no Node at the arena.

**Pydantic is the source of truth for the protocol (01.11).** Dashboard types come from it (`openapi-typescript`, `json-schema-to-typescript`). The agent repeats the same JSON with kotlinx.serialization.

**Headset identity = serial number + label + token (01.11).** See `docs/features/provisioning.md`. After a factory reset the headset is found by serial number and keeps its history.

**Commands live about 10 s (01.11).** A command for an offline headset must not run unexpectedly later.

## Protection and power

**Sleep is disabled only under protection (04.11).** Without protection a headset that was taken off goes to sleep and goes offline. We tried turning protection on in advance (agent 0.9.0) and removed it (user's decision).

**Protection only on a running game (04.11).** One switch on the dashboard: return to game + no sleep + power button lock + wake after a short press.

**No protection without our server (04.11).** After 30 s without connection the agent removes protection effects. 30 s so that a short Wi-Fi drop does not remove protection.

**No wake from the dashboard (04.11).** A sleeping headset is reachable for only about 2 minutes. Wake it with the button or by putting it on.

**No commands to a sleeping headset (07.11).** The server answers `failed / asleep` at once and does not wait for a timeout.

## Other

**UI in English (04.11). Everything in English (22.11).** Docs, comments, commits and chat replies too. Simple English, B1 with a little B2. Terms: headset, Protection, Sleep, Request access.

**One shared password for the dashboard (07.11).** See `docs/features/auth.md`.

**`update_agent` only through the setup endpoint (07.11).** Normal `/api/commands` can't send it (403).

**Agent signing key storage: postponed by the user.** Today the agent is signed with the debug key from `~/.android/debug.keystore` on the Mac. If this key is lost, installed agents can't be updated: only removed and set up again by cable. Decide before the pilot.
