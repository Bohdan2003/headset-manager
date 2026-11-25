# Sessions and statistics

## Sessions (server, `sessions.py`)

- A session opens when a game is in front. A game is anything that is not `com.oculus.`, `com.meta.`, `com.facebook.`, `com.android.` and not the agent.
- Exit to the menu and return to the same game within `session_grace_s` (60 s) = the same session, `exits + 1`.
- No return → end `exited` at the moment of exit.
- Another game → `switched`.
- `close_game` / `show_menu` with `ack` → `closed` / `menu`. For 10 s the server does not open a session again from an old heartbeat.
- `restart_game` → `restarted`, a new session opens at once. Power button restart → `power_button`.
- Connection lost → `offline`. Sessions still open after a server restart → `server_restart`.

## `GET /api/stats?period=today|7d|30d`

Periods start from local midnight.
- Totals.
- By game: time, sessions, average, exits, returns by protection, "left by player" / "ended by operator" (`restarted` counts as operator).
- By headset: time, sessions, drops.
- By day: sessions that cross midnight are split.

## Headset health (07.11)

The Statistics tab is about how each headset works: four bar charts, one bar per headset, the same headset order everywhere, a table below, and the games section after it. The agent was not changed for this, only server and dashboard.

- **Connection drops:** the headset disappeared by itself. Not counted: sleep (`asleep`: the headset was asleep when it disappeared), connection closed by the agent (`closed`: reboot, power off) and server stop. `disconnect` records without `screenOn` (before 07.11) are not counted: there sleep and drop can't be told apart (207 had 74 of these).
- **Charge interruptions:** charging stopped below 100 % (`charging` event, written since 07.11). If power was removed while the headset was offline, the server sees the change at the next heartbeat.
- **Battery life:** `100 / discharge %/h` over discharge parts without charging. Parts during sleep are not counted (`screenOn` in the `battery` event, since 07.11; older records count as awake). Measurements must be no more than 30 min apart.

## What we count

By headset and by game: play time, sessions, returns to the game (which games players "escape" from more often), battery wear, connection drops by headset (weak Wi-Fi zones), time from power on to `adb: ready`. **Not by player** (see ADR-0003).

## Next

Controller battery wear statistics. `controller_battery` events are already written. See `controllers.md`. Task: T-002.
