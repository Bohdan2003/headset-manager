# Protection (agent 0.9.1+)

One "Protection" switch on the dashboard. It joins: return to the game, no sleep when the headset is taken off, long power press lock, wake after a short press. The command is `guard`. The agent switches sleep and the button itself inside `Guard.set`.

## Rules

- Protection turns on only when a game is running (`guard {current: true}`). "Launch" with protection on protects the new game.
- **Sleep is disabled only under protection.** Without protection a headset that was taken off sleeps and goes offline.
- "Close game" turns protection off, but only after a successful close. Before `force-stop` the agent sets `Guard.hold(15 s)` so protection does not bring the game back.
- **No protection without our server.** After 30 s without connection the agent removes: return to game, button lock, sleep lock, button reaction. The setting itself stays. When the connection comes back, protection works again, and if the player is not in the game, the game starts. After the agent starts, protection does not work until the first connection to the server. The agent can't see the connection to the game's own server.
- Exit detection: on exit, events come from `com.oculus.vrshell`, `com.oculus.store`, `com.meta.systemui`. The game is back in ~3–4 s. Event `guard_relaunch`.

Checked on the headset (0.9.0): player exit → return; server stopped: protection still on after 12 s, removed after 40 s (button `SHUT_OFF`, sleep `DISABLED`, no return); server started → protection works again and returns the game.

## Power button under protection

- **Long press:** the agent writes `power_button_long_press = 0` and `power_button_very_long_press = 0` to `Settings.Global` (do nothing). When protection is off, it deletes them (factory behavior).
- **Short press (sleep)** can't be turned off by settings. The agent catches `ACTION_SCREEN_OFF` and wakes the headset with `input keyevent KEYCODE_WAKEUP` through local ADB.
- After a short press the game loses its connection to its own server. So the agent wakes the headset, closes the game and starts it again (`input keyevent KEYCODE_WAKEUP; am force-stop …`). Event `power_restart`. On the server the old session ends with `power_button` and a new one opens. The game restarts in ~0.3 s (0.8.0). Wake takes ~2.5 s.
- Needs ADB `ready`. Without it the headset can't be woken and stays asleep.
- A double press gives two restarts in a row.
- A ~10 s hold is a hardware power off. It can't be blocked.
- Optional idea: wake faster (2.5 s → ~0.5 s) with a wake lock that turns the screen on.

## Restart game

`restart_game` (local ADB): `force-stop` → check `pidof` → start again. Protection stays. Target: `pkg`, else the current game, else the protected game. On the server the old session ends with `end_reason = restarted` and a new one opens at once. In statistics it counts as "ended by operator".

## Dashboard

The switch shows on / off / partly for the selected headsets. On the card, protection is a 🛡 icon next to the current game. If the player is not in the protected game: 🛡 and its name. There is no separate sleep line: sleep is part of protection.
