---
name: device-check
description: Read-only health check of test headset 203 over adb (agent version, permissions, Accessibility, key timer, ADB keys). Only when the user asks.
disable-model-invocation: true
---

# Read-only check of headset 203

Only read commands. Nothing here changes the headset. Only 203 (`1WMHHA717K3282`). **Never 207.**

1. Find the headset: `adb devices -l`. Over Wi-Fi: `adb mdns services` (on Mac it may need a second try), then `adb connect <address>`. Use `-s <serial or address>` in every command.
2. Run and note the result:
   - Build: `adb -s … shell getprop ro.build.fingerprint`
   - Agent version: `adb -s … shell dumpsys package com.arena.agent | grep -E 'versionName|versionCode'`
   - Granted permissions: `adb -s … shell dumpsys package com.arena.agent | grep granted=true`
   - Accessibility: `adb -s … shell settings get secure enabled_accessibility_services` (must contain `com.arena.agent/com.arena.agent.WatcherService`)
   - Key timer: `adb -s … shell settings get global adb_allowed_connection_time` (want `0`)
   - Wireless debugging: `adb -s … shell settings get global adb_wifi_enabled`
   - Power button: `adb -s … shell settings get global power_button_long_press`
   - Agent running: `adb -s … shell pidof com.arena.agent`
   - Current game: `adb -s … shell dumpsys activity activities | grep 'ResumedActivity:'`
   - Controllers: `adb -s … shell dumpsys OVRRemoteService | grep -E 'Type:|Battery:|ExternalStatus'`
3. Long output (logcat, full dumpsys): save it to a file in the scratchpad and give it to the `log-reader` role.
4. Compare with `docs/quest-checks.md`. Write new or changed results there. Short summary to the user.

Never print private keys. `/data/misc/adb/adb_keys` holds only public keys: counting lines (`wc -l`) is fine, changing it is blocked by the hook.
The hook also blocks any command that contains the serial of headset 207, even `grep`.
