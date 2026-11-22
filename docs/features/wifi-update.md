# Agent update over Wi-Fi (agent 0.11.3, checked on headset 203)

Checked: 203 updated from 0.11.2 to 0.11.3 without a cable in 6 s.

The agent updates itself. No cable and no trust to the computer needed.

1. The `update_agent` command (`versionCode`, `sha256`, `path`) goes only through `POST /api/setup/update-wifi` from the server computer. Normal `/api/commands` can't send it (403).
2. The agent downloads `GET /api/agent/apk` and checks SHA-256.
3. It copies the file through local ADB to `/data/local/tmp`.
4. It sends `ack` and runs `pm install -r`, keeping the connection to adbd open (read timeout 3 min).
5. Android stops the agent at the end of the install. The new agent starts by itself.

- `nohup … &` does not work: the command did not run. adbd seems to end it together with the connection (0.11.0, no install log was created).
- Errors: event `update_failed` with a reason.
- Progress: `update_progress` events (`downloading` + percent, `installing`). The server keeps `update` in `HeadsetView` and sends it over `/live`, not to the event log. A new `hello` clears the field.
- Needs ADB `ready` on the headset. The first update to 0.11.2 must be by cable: older agents don't know this command (`needs_cable`).
- Android installs only an APK with the same signature and not a lower version.

## Manual update from a computer

`adb connect <port from adb mdns services>` + `adb install -r agent/app/build/outputs/apk/debug/app-debug.apk`. mDNS on Mac may need a second try. The agent restarts by itself after `adb install -r` (`MY_PACKAGE_REPLACED`).
