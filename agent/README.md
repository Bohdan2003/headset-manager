# agent: Android app on the headset (Kotlin)

Package `com.arena.agent`. It connects to the Arena server over WebSocket, reports the headset state and runs commands.

## Build

```bash
./gradlew assembleDebug    # app/build/outputs/apk/debug/app-debug.apk
```

Needs JDK 17 (`JAVA_HOME`) and the Android SDK. Signed with the debug key from `~/.android/debug.keystore`.
Headsets accept only an APK with the same signature.

## Install

- New headset: by cable, the Install button on the Setup tab in Arena (or `scripts/provision.sh`).
- Update: over Wi-Fi from the Setup tab, see `../docs/architecture/features/wifi-update.md`.

How it works: `CLAUDE.md` in this folder and `../docs/`.
