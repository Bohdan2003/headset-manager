# Local ADB on the headset (part C)

## Why we need adbd

A command runs with the rights of the user (uid) that started it. An app has few rights. The `shell` user (uid 2000) has many. The only way to get `shell` rights is through `adbd`. Android has no API for this. So the agent has a small ADB client inside (`LocalAdb.kt`, `MdnsFinder.kt`).

Without `shell` (only B) these do not work: reboot, wake, real game close. `killBackgroundProcesses` on Android 14 closes only the app's own processes. Without C, "close game" = show our menu over the game, and the game process stays in the background.

## The "Allow" dialog does not give access to the agent

The dialog only turns on the wireless debugging service. The service decides who may connect by the key list in `/data/misc/adb/adb_keys`. The agent's key gets there during setup, only with the "Always allow from this computer" checkbox. Without it: `CERTIFICATE_VERIFY_FAILED`.

## Order on every boot

1. Wait for Wi-Fi.
2. Write `adb_wifi_enabled = 1` (needs `WRITE_SECURE_SETTINGS`).
3. Wait until the operator taps "Always allow on this network". Status `waiting_confirmation`, no time limit.
4. Find the port through mDNS `_adb-tls-connect._tcp`. The port is new every time. mDNS can also return an old record with a dead port, so try all of them.
5. Log in to `127.0.0.1:<port>` by TLS 1.3 with the agent's key → `adb: ready`.

`prox_close` (lost on boot) does not need ADB: the agent sends a normal broadcast right after start, if protection is on.

**Why wait for Wi-Fi.** `adb_wifi_enabled = 1` survives a reboot, but about 20 s after boot the system checks it before Wi-Fi connects and resets it to `0` (`Not connected to any wireless network. Not enabling adbwifi`). Data goes through `127.0.0.1`, but Android does not turn on debugging without Wi-Fi.

**Why the dialog on every boot.** Quest **does not remember** "Always allow on this network" after a reboot (same BSSID; on boot `AdbDebuggingManager: Ignoring tag 'null'`, looks like a Meta bug, firmware from 25.09.2026 is current). Within one boot it remembers: turning debugging on again and Wi-Fi drops do not show the dialog. The Accessibility service can't tap the dialog: Quest does not send it events from this window (checked 01.11). Ideas for later: poll windows on a timer; report the bug to Meta.

**Wi-Fi drop.** Android turns off debugging (`Wifi disabled. Disabling adbwifi`) and does not turn it on again. The agent listens for the network (`ConnectivityManager.NetworkCallback`), writes `adb_wifi_enabled = 1` again (no dialog), then finds the new port.

**Request access.** The `request_access` command writes `adb_wifi_enabled` 0, then 1 after 1 s, and the dialog appears again. If access is already `ready`, the agent does nothing (it would reset access). The agent repeats the request by itself every 5 minutes. Not checked on a headset.

## What the operator does

1. **Once per headset, by cable:** setup (see `provisioning.md`). In the headset, tick "Always allow from this computer".
2. **After every power on or reboot:** put on the headset and tap **"Always allow on this network"**. Not "Allow": "Allow" works once, and after the first Wi-Fi drop the dialog comes back (checked 01.11).
3. **If the key is lost** (status `key_rejected`): set up again by cable.

## Key timer (7 days)

Android removes a trusted key if it was not used for `adb_allowed_connection_time` ms (default 604800000 = 7 days; in the log `authWindow = 604800000`; not set on our headset). The count starts from the last connection.

1. Setup: `settings put global adb_allowed_connection_time 0`.
2. The agent on every start reads `Settings.Global`. If it is not `0`, it writes `0` with `Settings.Global.putLong`. No permission → `adbTimeoutDisabled: false`.
3. `adbTimeoutDisabled` goes in `heartbeat`. The dashboard warns if it is `false`.

## Implementation notes

- No helper process. Commands go straight to `adbd`. The agent reconnects before a command if the connection is gone.
- C commands run in a separate thread. First try the last working port, then mDNS.
- Login to adbd takes about 2 s. Most of the time of "close game" and "wake" is this login.
- `LocalAdb.shell()` sometimes returned empty or shifted output in the spike app. Check if the agent still has this.
