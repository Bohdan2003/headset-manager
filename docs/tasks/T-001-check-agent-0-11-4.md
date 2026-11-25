# T-001: Check agent 0.11.4 on headset 203

- **Role:** main session
- **Status:** review
- **Priority:** high
- **Output:** rows in `docs/research/quest-checks.md`

## Context

The code is written (22.11, bugs from the Windows test). Headsets still run 0.11.3. Two fixes, both causes are likely but not confirmed:

- **Charging:** the card said "not charging" while power was connected. Now the agent also sends `plugged`, and the card shows "plugged in, not charging". Likely cause: a weak power source gives Android status `NOT_CHARGING`.
- **Close game** after "launch A, launch B" gave an error on the card. Now "Close game" closes every running game in one adbd session. Likely cause (the error text was not seen): the agent closed only the game it thought was in front, and that value can be stale.

## What to do

1. Update 203 to 0.11.4 (skill `/update-agent-wifi`, the user types it and says "yes").
2. Plug 203 into a PC USB port.
3. Launch A, launch B, then Close game.

## Acceptance criteria

- [ ] 203 runs 0.11.4.
- [ ] The card shows "plugged in, not charging" on a PC USB port.
- [ ] After Close game: our menu, `pidof` is empty for both games, the card is green.
- [ ] Both causes are confirmed or marked as not confirmed.

## Log

- 2026-11-25: task created from `docs/status.md`.
- 2026-11-25: preparation only, no command was sent to a headset. `app-debug.apk` is 0.11.4 (22), same file as `packaging/prebuilt/agent.apk`, sources did not change since `d3ee486`. The Close game script works in a local simulation with fake `pm`, `pidof` and `am` (two games, no game, a game that does not close): this is not a headset check.
- 2026-11-25: can't check yet. 203 is registered only in the Arena program database (the dev server does not know it), but `dist/Arena.app` still contains 0.11.3, so rebuild it first. The Mac is on 192.168.1.x, headsets connected from 192.168.50.x. No server is running.
