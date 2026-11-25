# ADR-0005: Two levels on the headset: B and C

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related:** ADR-0004, ADR-0008

## Context

Some actions work with normal app permissions. Others need the rights of the `shell` user, and only local ADB gives them.

## Decision

Split the agent into two levels. B = normal app permissions, given once by cable: online, battery, current game, launching games, our menu, return to the game, sleep control. C = local ADB: the agent logs in to `adbd` on the headset with its own key, only for strong commands (close game, reboot, wake, power off, install).

## Consequences

- B is the base of the product. It never depends on C or on the key.
- Without C the agent answers `ack { ok: false, reason: "no_adb" }`.
- "Wake" is used only by the agent itself under protection (ADR-0019).
- **Checked by:** `test_failed_ack_keeps_reason` checks that the server keeps the reason. "B works without C" has no automatic check: it is checked by hand on headset 203.

## Alternatives considered

Not recorded.
