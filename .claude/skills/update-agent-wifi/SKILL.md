---
name: update-agent-wifi
description: Build a new agent and update it on test headset 203 over Wi-Fi. Changes the headset, so only when the user asks.
disable-model-invocation: true
---

# Update the agent on headset 203 over Wi-Fi

Details: `docs/features/wifi-update.md`. Only headset 203 (`1WMHHA717K3282`). **Never 207.**

1. **Check the version.** `versionName` and `versionCode` in `agent/app/build.gradle.kts` must be higher than on the headset (the dashboard shows the headset version). Android does not install a lower version.
2. **Build.** `cd agent && ./gradlew assembleDebug`. It must be signed with the same debug key (`~/.android/debug.keystore` on this Mac).
3. **Which server serves the APK.**
   - Dev server (`./scripts/start.sh`): it serves `agent/app/build/outputs/apk/debug/app-debug.apk` at once.
   - Arena program: it serves the APK bundled inside. Rebuild the program (`cd server && uv run python ../packaging/build.py`), this also updates `packaging/prebuilt/`. Restarting the program breaks headset connections for a moment: tell the user.
4. **Check the headset.** It is online, awake, and ADB is `ready`. If it waits for confirmation, ask the user to tap "Always allow on this network".
5. **Ask the user "yes"**: "I will update the agent on 203 from X to Y over Wi-Fi."
6. **Start.** The Update button on the Setup tab, or `POST /api/setup/update-wifi` from the server computer.
7. **Watch.** `update_progress` (downloading %, installing), then a new `hello` with the new version. On error: the `update_failed` event and its reason.
8. **Record.** Update `docs/status.md`. If `packaging/prebuilt/` changed, say that it must be committed (CI checks the version).
