# Protocol and data

Source of truth: `server/src/headset_server/protocol.py`. If this file and the code disagree, the code wins. Fix this file.

JSON fields are camelCase (`headsetId`), Python fields are snake_case (`headset_id`).

## Agent ↔ server (`WS /agent`)

| Message | Direction | Content |
|---|---|---|
| `hello` | agent → server | `headsetId`, `token`, `agentVersion`, `androidId` |
| `welcome` | server → agent | server time, `heartbeatIntervalS`, `guardPkg` (protected game) |
| `heartbeat` | agent → server, every 5 s | `battery`, `charging`, `plugged`, `temp`, `currentPkg`, `adb`, `sleepDisabled`, `adbTimeoutDisabled`, `guardPkg`, `screenOn`, `controllers` |
| `event` | agent → server | `kind` + `payload`, see below |
| `apps` | agent → server | installed apps: `package`, `title`, `vr` |
| `command` | server → agent | `id`, `cmd`, `params`, `ttlS` (default 10) |
| `ack` | agent → server | `id`, `ok`, `reason`, `detail` |

`controllers`: `[{side: "left"|"right", battery, connected}]`. `null` means the agent could not read them.
`screenOn: false` means the headset is asleep. `null` means an old agent.
`charging` = the battery is filling up. `plugged` = power is connected (agent 0.11.4+, `null` from older agents). A weak power source gives `plugged: true, charging: false`.

## Commands

| `cmd` | Level | What it does |
|---|---|---|
| `launch` | B | Start a game (`pkg`). With protection on, the new game becomes protected |
| `show_menu` | B | Show our waiting screen `MenuActivity`, removes protection |
| `guard` | B | Protection on/off (`{current: true}` = protect the current game) |
| `set_sleep` | B | Sleep on/off. Still in the protocol, the dashboard does not send it |
| `request_access` | B | Show the "Allow wireless debugging" dialog again. Does nothing if ADB is already `ready` |
| `close_game` | C | No `pkg`: `force-stop` **every** running game (from `pm list packages -3` + `pidof`), check `pidof`, show our menu, then protection off. No game running is not an error. With `pkg`: only that game |
| `restart_game` | C | `force-stop` + start again, protection stays |
| `reboot` | C | Check login to adbd, send `ack`, reboot after 1.5 s |
| `sleep` | C | `input keyevent KEYCODE_SLEEP` (does not trigger restart under protection) |
| `power_off` | C | `reboot -p` |
| `update_agent` | C | Only through `POST /api/setup/update-wifi`, see `features/wifi-update.md` |

Level C without ADB → `ack { ok: false, reason: "no_adb" }`.

## Statuses and reasons

- `adb` in `heartbeat`: `ready` · `no_wifi` · `waiting_confirmation` (dialog not confirmed) · `connecting` · `key_missing` · `key_rejected` · `error`.
- Command status: `sent → acked | failed | timeout`. No `ack` within `ttl + 5 s` → `timeout`.
- Command reason: `offline`, `asleep`, `timeout` (set by the server); `no_adb`, `not_allowed`, `failed`, `expired`, `bad_params` (sent by the agent).

## Events (`event.kind` and server events)

`connect`, `disconnect`, `game_start`, `game_exit`, `guard_relaunch`, `power_restart`, `adb_status`, `battery`, `charging`, `controller_battery`, `update_progress`, `update_failed`.
`update_progress` is not written to the event log. The server keeps it in `HeadsetView.update` and sends it over `/live`.

## Dashboard → server (REST)

- `POST /api/commands` `{headsetIds, cmd, params}`: params are checked per command, package by `^[a-zA-Z0-9_.]+$`. One command per headset. Offline → `failed / offline` at once, asleep → `failed / asleep`. Statuses and the last commands go to `/live`.
- `GET/POST /api/headsets`, `PATCH /api/headsets/{id}` (`{label}`), `GET /api/stats?period=…`, `/api/setup/*`, `/api/auth/*`. Full list: `GET /docs` (Swagger).

## Server → dashboard (`WS /live`)

First `{"type": "snapshot", "headsets": [...]}`, then `{"type": "headset", "headset": {...}}` and `{"type": "command", ...}` on changes.

## Database tables

| Table | Fields |
|---|---|
| `headsets` | `id`, `label`, `serial` (unique), `android_id`, `token_hash`, `created_at` |
| `headset_state` | `headset_id`, `online`, `battery`, `charging`, `temp`, `current_pkg`, `adb`, `sleep_disabled`, `agent_version`, `last_seen`, `guard_pkg` |
| `headset_apps` | installed apps per headset |
| `commands` | `id`, `headset_id`, `cmd`, `params`, `status`, `reason`, `created_at`, `acked_at` |
| `events` | `headset_id`, `ts`, `type`, `payload` (JSON) |
| `sessions` | `headset_id`, `package`, `started_at`, `ended_at`, `end_reason`, `exits`, `guard_returns` |
