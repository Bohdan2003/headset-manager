# Setting up a headset by cable

Two implementations of the same steps exist today: `scripts/provision.sh` and `server/src/headset_server/setup_tools.py` (the Setup tab in Arena). Change both together, or better, make one call the other. Neither was fully checked on a second headset.

## Steps

1. `adb install -r` the agent.
2. `pm grant ... WRITE_SECURE_SETTINGS`, `DUMP` and other permissions. `appops set com.arena.agent GET_USAGE_STATS allow`.
3. Turn on the agent's Accessibility service: `settings put secure enabled_accessibility_services ...` + `accessibility_enabled 1`.
4. Key timer: `settings put global adb_allowed_connection_time 0`.
5. `adb keygen` into a temporary folder.
6. Start the adb server so that the headset sees **only** this key (see "Key swap" below).
7. The operator ticks "Always allow from this computer" in the headset.
8. Check in `logcat`: `AdbDebuggingManager ... alwaysAllow = true`. If not, stop.
9. Send the key, the certificate, `headsetId`, token and server address to the agent by broadcast to a receiver with `android:permission="android.permission.DUMP"` (PKCS#8 DER + X.509 DER, base64).
10. Delete the key files from the computer.
11. Reboot. The operator taps "Always allow on this network". Wait for `adb: ready`.

## Key swap

adb looks for the key only in `<home folder>/.android/`. It does not read `ANDROID_USER_HOME` (checked with adb 1.0.41). On Mac you can change the folder with `HOME`. On Windows adb takes the profile folder from the system and variables do not help. So Arena moves the computer's key to `.android/arena-computer-key/` for the time of setup, puts the headset key in its place, and then moves it back. After a crash it moves it back on start.

While this is going on, Arena does not call `adb` for the device list: the adb server is using the temporary key.

## Certificate

Self-signed, like `adb`'s: `C=US, O=Android, CN=Adb`, `basicConstraints=critical,CA:TRUE`, `keyUsage=critical,keyCertSign,cRLSign,digitalSignature`, `subjectKeyIdentifier=hash`.

`DUMP` is a `development` permission. Any app can get it through `pm grant`. So "only `shell` can send" is not an absolute guarantee.

## Headset identity

- Setup reads the **serial number** (`adb shell getprop ro.serialno`; the app itself can't read it). The operator types a **label** ("Headset 07", a sticker on the body).
- The server creates a record and gives the agent `headsetId` + a secret **token** (the server stores only the hash).
- The agent sends `headsetId` + token on every connection. Another device can't pretend to be our headset.
- After a factory reset, setup finds the headset by serial number and links it to the same record. History and statistics stay.
- `ANDROID_ID` is a helper field. The agent reads it itself: the app's value is different from `adb shell settings get secure android_id` (checked: `c1f36e29…` vs `efbbca1c…`). It changes after a factory reset.
- Running setup again overwrites the label with the one given in the command.
- The label can also be changed on the dashboard card: `PATCH /api/headsets/{id}` `{label}`, 1–64 characters.

## Setup tab in Arena

Shows headsets visible in `adb`, agent version on the headset and in the program, status. Buttons: Install (asks for a label, USB only), Update/Reinstall, Remove. Works only from the server computer.
The list comes from the registry: version from `hello`, status from `fleet_status`.
**Install, Update and Remove were not checked on a real headset.**
