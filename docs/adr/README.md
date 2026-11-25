# ADR: log of architecture decisions

ADR = a short file about one decision and its reason.
One decision = one file `NNNN-kebab-case-title.md`. Numbers are never reused.
A decision is not made until its status is `Accepted`. If you want to change one, first read why it was made, then write a new ADR that replaces it.

ADRs 0001–0024 were moved from `docs/decisions.md` on 2026-11-25. Where the old file had no alternatives or no date, the ADR says "not recorded". Do not guess them.

## Format

```markdown
# ADR-NNNN: short title

- **Status:** Proposed | Accepted | Superseded by ADR-NNNN | Rejected
- **Date:** YYYY-MM-DD
- **Related:** T-NNN, ADR-NNNN

## Context

What hurts. Facts and measurements, not impressions.

## Decision

What we do. One paragraph, written as an order.

## Consequences

What gets better, what gets worse.
Last line, **Checked by:** the test or the CI step that checks the decision. If there is none, say so.

## Alternatives considered

Option: why it was rejected.
```

## Index

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-own-implementation.md) | Own implementation, no MDM | Accepted |
| [0002](0002-no-device-owner.md) | No Device Owner | Accepted |
| [0003](0003-no-statistics-per-player.md) | No statistics per player | Accepted |
| [0004](0004-no-adb-from-server.md) | The server does not control headsets over ADB | Accepted |
| [0005](0005-two-levels-b-and-c.md) | Two levels on the headset: B and C | Accepted |
| [0006](0006-named-commands.md) | The server sends meanings, not shell | Accepted |
| [0007](0007-no-adb-keys-on-server.md) | No ADB keys on the server | Accepted |
| [0008](0008-no-helper-process.md) | No helper process | Accepted |
| [0009](0009-always-allow-on-this-network.md) | "Always allow on this network", not "Allow" | Accepted |
| [0010](0010-unknown-usb-key.md) | Never approve the USB debugging dialog with an unknown key | Accepted |
| [0011](0011-python-fastapi-one-process.md) | Python, FastAPI and SQLite in one process | Accepted |
| [0012](0012-react-vite.md) | React and Vite, not Next.js | Accepted |
| [0013](0013-pydantic-source-of-truth.md) | Pydantic is the source of truth for the protocol | Accepted |
| [0014](0014-headset-identity.md) | Headset identity: serial number, label and token | Accepted |
| [0015](0015-commands-live-10s.md) | Commands live about 10 seconds | Accepted |
| [0016](0016-sleep-only-under-protection.md) | Sleep is disabled only under protection | Accepted |
| [0017](0017-protection-on-running-game.md) | Protection only on a running game | Accepted |
| [0018](0018-no-protection-without-server.md) | No protection without our server | Accepted |
| [0019](0019-no-wake-from-dashboard.md) | No wake from the dashboard | Accepted |
| [0020](0020-no-commands-when-asleep.md) | No commands to a sleeping headset | Accepted |
| [0021](0021-english-everywhere.md) | Everything in English | Accepted |
| [0022](0022-one-dashboard-password.md) | One shared password for the dashboard | Accepted |
| [0023](0023-update-agent-only-from-setup.md) | `update_agent` only through the setup endpoint | Accepted |
| [0024](0024-agent-signing-key.md) | Where to keep the agent signing key | Proposed |
