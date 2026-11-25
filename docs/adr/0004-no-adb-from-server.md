# ADR-0004: The server does not control headsets over ADB

- **Status:** Accepted
- **Date:** 2026-10-31
- **Related:** ADR-0005, ADR-0007

## Context

`adb tcpip` is lost after a headset reboot, and only a cable brings it back (tested 31.10).

## Decision

Do not use ADB from the server to control headsets. Only `setup_tools.py` may call adb, for setup and updates by cable on the server computer.

## Consequences

- Strong commands need local ADB inside the headset (ADR-0005).
- **Checked by:** no automatic check. `reviewer` looks for it in the diff.

## Alternatives considered

`adb tcpip` from the server, with `@devicefarmer/adbkit` — rejected: access is lost on every reboot.
