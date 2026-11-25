# Controller battery (agent 0.6.0+)

Quest shows controller battery only in `dumpsys OVRRemoteService`. Lines look like `Paired device: … Type: Right … Battery: 40% … ExternalStatus: CONNECTED_ACTIVE`. A controller that is off shows `SEARCHING` with the last known battery.

- Once a minute the agent reads it: first by itself (`dumpsys` from the agent process, needs the `DUMP` permission from setup), else through local ADB.
- It sends `controllers: [{side, battery, connected}]` in heartbeat. `null` = could not read.
- The server keeps it in memory and writes a `controller_battery` event when the battery of a connected controller changes.
- Dashboard: a battery bar for each controller, like the headset's. A controller that is off is grey, "· off", with the last known battery. The "Battery < 20%" tile also counts connected controllers.

## Next (T-002, priority 1)

Controller battery wear statistics from `controller_battery` events. Server + dashboard only. The agent already sends everything.
