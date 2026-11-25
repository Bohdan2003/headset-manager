# Sleep, power and charging

## Sleep control

- `prox_close` broadcast from a normal app → `Virtual proximity state: CLOSE` (no sleep). `automation_disable` → back to normal. Lost on reboot.
- From agent 0.7.0 sleep is disabled only under protection (before that, on every agent start). Right after start the agent sets sleep to match protection: `prox_close` under protection, otherwise `automation_disable`.

## Sleep and power off from the dashboard (agent 0.10.1)

- `sleep`: `input keyevent KEYCODE_SLEEP` through local ADB. Under protection it does not cause a game restart (`Guard.expectSleep`).
- `power_off`: `reboot -p`. The dashboard asks for confirmation.
- The agent sends `screenOn` (`PowerManager.isInteractive`). The card shows "asleep".
- **No wake from the dashboard.** The headset stays reachable only ~2 minutes of sleep (checked 04.11: `wake` worked after ~1 min; after 2 min the connection was gone, ping and ADB did not answer; maybe `wifi_power_save=120`, not checked). Wake it with the button or by putting it on.

## Sleeping headset (07.11)

Commands are not sent to a sleeping headset (`screenOn = false`). The server answers `failed / asleep` at once. On the dashboard the buttons are disabled if only sleeping headsets are selected. The card says "Asleep: commands unavailable".

On charge, a sleeping headset appears and disappears from the network about once a minute (Wi-Fi is not fully off during sleep on charge). Connection drops in statistics are higher because of this.

## Reboot

`reboot`: the agent first checks login to adbd (`id`), sends `ack`, and reboots after 1.5 s (after the reboot it can't send the ack). Before rebooting the agent closes the connection itself, so the server sees offline at once. If there was no reboot after 10 s, it reconnects.

After a reboot: the agent starts by itself and is online in ~30 s with `waiting_confirmation` → after "Always allow on this network" it is `ready` in ~2 s.

## Charging (agent 0.8.1)

Headsets have power banks. Next to the battery percent the card shows one of:
- "71% · charging": the battery is filling up (`charging`, Android status `CHARGING` or `FULL`);
- "71% · plugged in, not charging": power is connected but the battery does not fill up (`plugged: true, charging: false`, agent 0.11.4+). A weak source does this: a PC USB port or a weak power bank cannot cover a headset in use. Android then reports `NOT_CHARGING`. Before 0.11.4 the card showed only "not charging" here (found in the Windows test, 22.11);
- "71% · not charging": no power.

When power is plugged in or out, the agent sends a heartbeat after 1 s (the status needs a moment to update).
Statistics ("charge interruptions") still use `charging`, not `plugged`.
