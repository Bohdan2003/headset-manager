# After a Meta firmware update

Run this on headset 203 after every Meta OS update, before updating other headsets. Write results into `quest-checks.md`.
Steps 1, 4, 5 and 9 only read. The other steps change the headset state: ask the user before each one.

1. Build number: `adb shell getprop ro.build.fingerprint`. Note it in `quest-checks.md`.
2. **Starting screens from the background (most risky).** Launch a game, `show_menu` and protection return from the dashboard. Check logcat for `BAL` lines. If Android blocks them, menu, launch and protection stop working.
3. Agent starts after reboot by itself (`BOOT_COMPLETED`) and comes online.
4. Accessibility service is still on: `adb shell settings get secure enabled_accessibility_services`.
5. Granted permissions are still there: `adb shell dumpsys package com.arena.agent | grep granted=true`.
6. After "Always allow on this network" the status becomes `ready`. Check if the dialog is still shown on every boot (maybe Meta fixed it).
7. `prox_close` still disables sleep.
8. Power button settings still work (long press does nothing under protection).
9. Controller battery is still in `dumpsys OVRRemoteService`.
10. Current game is still detected from Accessibility events.
