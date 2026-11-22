# agent: Android app on the headset (Kotlin)

Package `com.arena.agent`. Version in `app/build.gradle.kts` (`versionName`, `versionCode`). Raise both on every change that goes to headsets.

## Safety rules (read before any change)

- The server sends only named commands. Each command maps to a **prepared** shell command in the agent. Never run a shell string that came from the network.
- Check every package name with `^[a-zA-Z0-9_.]+$` before it goes into a shell command.
- System packages (`com.oculus.`, `com.meta.`, `com.facebook.`, `com.android.`) can't be closed.
- Never log private keys or tokens.
- Do not run `adb` against a headset from a subagent. Build only (`./gradlew assembleDebug`). The main session installs, after the user says "yes".
- Never `am force-stop com.arena.agent` (see root `CLAUDE.md`).

## How it works

- Foreground service, starts on `BOOT_COMPLETED`. Restarts after an update (`MY_PACKAGE_REPLACED`).
- WebSocket with OkHttp. Reconnect pause 1 → 2 → 5 … 30 s. Server address is fixed at setup.
- Right after start: set sleep to match protection (`prox_close` under protection, else `automation_disable`).
- Current game: from Accessibility events (`WatcherService`). After an agent restart: from usage statistics, taking the open game if there is one (on Quest the last window is often a Meta panel over the game).
- Installed apps (`apps`) after connecting. VR apps are marked by category `com.oculus.intent.category.VR`. Needs `<queries>` for `MAIN/LAUNCHER` and for this category.
- Part B = normal permissions. Part C = `LocalAdb` + `MdnsFinder`, see `docs/features/adb-access.md`.
- C commands run in a separate thread.

## Files (`app/src/main/java/com/arena/agent/`)

| File | What |
|---|---|
| `AgentService.kt` | Foreground service, main loop |
| `ServerConnection.kt` | WebSocket, hello, heartbeat, reconnect |
| `Commands.kt` | `CommandExecutor` (command → prepared action, `ack`), `Launcher`, `MenuActivity` (our waiting screen) |
| `AdbManager.kt`, `LocalAdb.kt`, `MdnsFinder.kt`, `AdbKey.kt` | Part C: debugging on, port, TLS login, key |
| `Device.kt` | Battery, `Sleep`, `CurrentApp`, `PowerLock` (power button), `Guard` (protection), `WatcherService` (Accessibility) |
| `Controllers.kt` | Controller battery from `dumpsys OVRRemoteService` |
| `Receivers.kt` | Boot, update, setup broadcast (needs `DUMP`), power |
| `AgentApp.kt`, `AgentLog.kt` | App start, log |

Note: on Mac git does not see letter case. `.gitignore` has `adbkey*` and `!AdbKey.kt`, so the source file is not lost.

## Feature docs

`docs/features/protection.md`, `power.md`, `controllers.md`, `wifi-update.md`, `adb-access.md`. Device checks: `docs/quest-checks.md`.

## Risk

Starting screens from a background service logs `With BAL hardening this activity start would be blocked!`. Allowed today (`BAL_ALLOW_PERMISSION`). Future Android versions may block menu, launch and protection. Check first after a firmware update (`docs/firmware-checklist.md`).

## Signing

Signed with the debug key `~/.android/debug.keystore` on the Mac. If it is lost, installed agents can't be updated, only removed and set up again by cable.
