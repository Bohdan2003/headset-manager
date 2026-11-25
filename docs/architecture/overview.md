# Target architecture

> This file and the accepted ADRs say how the system must be built. It changes only through an ADR.
> One exception: the protocol. There the code `protocol.py` is the source of truth (ADR-0013).

## Parts

```
Arena computer (one program, one port, local network, no internet)
├─ server/     Python, FastAPI, SQLite. WS /agent for headsets, REST /api + WS /live for the dashboard
├─ dashboard/  React + Vite + TypeScript + Tailwind. FastAPI serves its build on "/"
└─ packaging/  Arena.app / Arena.exe: server + dashboard + adb + agent.apk in one program
                        │ WebSocket over Wi-Fi
agent/  Kotlin app on every headset
├─ B: normal app permissions
└─ C: local ADB inside the headset
```

`spike/` is an old test app. It is not used in the product.

## Rules between the parts

| Rule | ADR |
|---|---|
| The server never controls headsets over ADB and stores no ADB keys | 0004, 0007 |
| B works without C | 0005 |
| The server sends named commands, the agent maps them to prepared shell commands | 0006 |
| One uvicorn process | 0011 |
| Protocol order: server → generated types → dashboard and agent | 0013 |
| A headset connects with its id and secret token | 0014 |
| `update_agent` only from the server computer | 0023 |

## Where data lives

- Online headsets and open WebSockets: memory of the server process.
- History, tokens (only hashes), commands, sessions: SQLite. Tables are in [protocol.md](protocol.md).
- ADB key: only inside the agent on its headset.
- The Arena program and `./scripts/start.sh` use different databases. Never delete the database: it holds headset tokens.

## More detail

- Messages, commands, statuses, tables: [protocol.md](protocol.md).
- One file per feature: [features/](features/).
- How each part is built inside: `CLAUDE.md` and `README.md` in `server/`, `dashboard/`, `agent/`, `packaging/`.

## Risk to watch

After a Meta firmware update run [the checklist](../research/firmware-checklist.md) first. Starting screens from the background may get blocked (`BAL hardening`).

## Open questions

| Topic | Decided in |
|---|---|
| Where to keep the agent signing key | ADR-0024 (Proposed), T-008 |
| One implementation of setup instead of two | no ADR yet, T-009 |
