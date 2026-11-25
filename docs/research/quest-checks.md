# Checks on our Quest

Write every new result here: command → works / does not work / what it returned.

Test headset: 203 (`1WMHHA717K3282`). **Never 207 (`1WMHH868671295`).**
Headset: Quest 2, Android 14, build `52242990035800150` (`UP1A.231005.007.A1`), built 25.09.2026.

## Shell and ADB

| Check | Result |
|---|---|
| Current game through shell | ✅ `dumpsys activity activities \| grep 'ResumedActivity:'` (not `topResumedActivity`: there is one per shell panel) |
| Disable sleep | ✅ `prox_close` → `Virtual proximity state: CLOSE`; `automation_disable` returns normal behavior. Lost after reboot |
| `adb tcpip 5555` survives reboot | ❌ |
| Key with "Always allow" opens wireless debugging without pairing | ✅ (without the checkbox ❌ `CERTIFICATE_VERIFY_FAILED`) |
| Key with "Always allow" survives reboot | ✅ 01.11 (keys `1525…` and `EF61…`, checked one key at a time). ⚠️ On 31.10 key `EE4D…` disappeared from `adb_keys` within one hour between two reboots. Reason unknown. Watch this in the pilot. Check with one key only: adb on Mac offers several at once |
| Through wireless debugging: `id`, `monkey`, `force-stop`, `reboot`, `prox_close` | ✅ `uid=2000(shell)`, all work |
| Wireless debugging turns on by itself after boot | ❌ reset before Wi-Fi connects |
| "Always allow on this network" after reboot | ❌ dialog on every boot, even on the same BSSID |
| "Always allow on this network" within one boot | ✅ turning debugging on again and Wi-Fi drops: no dialog |
| Debugging after a Wi-Fi drop | comes back only after writing `adb_wifi_enabled = 1`, the port is new |
| `killBackgroundProcesses` for another app's game | ❌ the process stays |
| Permissions from `pm grant` and Accessibility after reboot | ✅ |

## The agent as a normal app (B)

| Check | Result |
|---|---|
| `WRITE_SECURE_SETTINGS` → `adb_wifi_enabled = 1` | ✅ |
| Port through `NsdManager` | ✅ (returns the old record and the new "... (2)") |
| Login to adbd on `127.0.0.1` by TLS, `id`, `prox_close` | ✅ |
| Accessibility clicks the "Allow wireless debugging" dialog | ❌ no events from this dialog |
| Broadcast to a receiver with `DUMP` from `shell` | ✅ |
| `sendBroadcast(Intent("com.oculus.vrpowermanager.prox_close"))` from a normal app | ✅ sleep control does not need `shell` |
| Current game from Accessibility `TYPE_WINDOW_STATE_CHANGED` | ✅ (`pkg=com.Anvio.CityZ`). Polling the window list does not see the game: an immersive game window is not in it |
| Launch a game from the background (no visible window, Accessibility on) | ✅ needs `<queries>` with `MAIN/LAUNCHER`, otherwise `getLaunchIntentForPackage` → `null` |
| Return to the game after going home | ✅ back in ~4 s. Events on exit come from `com.oculus.vrshell`, `com.oculus.store`, `com.meta.systemui` |
| Permissions and Accessibility survive reboot and `adb install -r` | ✅ |
| `dumpsys OVRRemoteService` from the agent with `DUMP` | ✅ controller battery |
| Start `MenuActivity` from a background service | ✅ but logs `With BAL hardening this activity start would be blocked!` (allowed now by `BAL_ALLOW_PERMISSION`) |

## Power button

Policy (`dumpsys window policy`): short press `SHORT_PRESS_POWER_GO_TO_SLEEP`, long `LONG_PRESS_POWER_SHUT_OFF`, very long `VERY_LONG_PRESS_POWER_OFF`.

| Check | Result |
|---|---|
| `power_button_long_press = 0` and `power_button_very_long_press = 0` | ✅ long press does nothing (`LONG_PRESS_POWER_NOTHING`), holding acts like a short press |
| Turn off short press by settings | ❌ only firmware config (`mShortPressOnPowerBehavior=1`) |
| Wake after short press with `input keyevent KEYCODE_WAKEUP` | ✅ ~2.5 s (almost all of it is the adbd login) |
| Hold ~10 s | hardware power off, can't be blocked |
| Wake over network during sleep | works ~1 min, after ~2 min ping and ADB stop (maybe `wifi_power_save=120`, not checked) |

## Whole features checked on a real headset

- Server, protocol, registry, `/live`, dashboard list and summary tiles.
- B commands: launch, protection (return to game, sleep, power button), our menu.
- C commands: close game, restart game, reboot, sleep, power off. (Close game was changed in 0.11.4, not checked again: T-001.)
- Agent starts after reboot by itself, comes back after Wi-Fi drops.
- Controller battery in heartbeat and on the dashboard.
- Statistics: sessions, games, headset health (drops, charge interruptions, battery life).
- Agent update over Wi-Fi (203: 0.11.2 → 0.11.3 in 6 s).
- Dashboard login with one password.

The test app `com.arena.adbprobe` on the headset is disabled (`pm disable-user`), not removed.

## Not checked yet

Tasks: T-001, T-005, T-006, T-007, T-013.

- Agent 0.11.4: `plugged` on a PC USB port, Close game after "launch A, launch B".
- `adb_allowed_connection_time = 0` really keeps the key (needs 8+ days without connections).
- The "Allow wireless debugging" dialog when the headset moves to another access point.
- Auto-click of "Allow" by polling windows on a timer (code is in `spike/adb-probe`).
- `request_access` on a real headset.
- Install, Update and Remove from the Setup tab on a real headset.
