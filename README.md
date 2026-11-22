# Arena

An internal tool to manage the Meta Quest headsets at our VR arena from one dashboard.
It works in the local network and does not need the internet.

With Arena an operator can:
- see every headset: online or not, battery, controllers, current game, asleep or awake;
- start a game on many headsets at once;
- turn on Protection: the player is brought back to the game if they leave it, and the headset does not sleep;
- close or restart a game, reboot, sleep or power off a headset;
- see statistics: play time per game, connection drops, battery life per headset;
- set up new headsets by cable and update the headset app over Wi-Fi.

## How it works

```
Arena computer                                   Headsets
┌────────────────────────────────┐   Wi-Fi   ┌──────────────────────┐
│ Arena program                  │◄─────────►│ agent (Android app)  │
│  server  (Python, FastAPI)     │ WebSocket │  on every headset    │
│  dashboard (React, in browser) │           └──────────────────────┘
└────────────────────────────────┘
```

- **server** keeps the list of headsets, sends commands and stores statistics (SQLite).
- **dashboard** is the web page operators use: http://<arena computer>:8000.
- **agent** runs on each headset. It reports the headset state and runs commands from the server.

## Quick start

**At the arena:** double click the Arena program (`Arena.app` on Mac, `Arena.exe` on Windows).
It starts the server and opens the dashboard. The first time, you set a dashboard password.

**For development:**

```bash
./scripts/start.sh                # server + dashboard on http://localhost:8000
```

Without a real headset you can use fake ones:

```bash
cd server && HM_ADMIN_TOKEN=dev-admin uv run python tools/fake_agent.py --count 3
```

## Daily work with headsets

1. **New headset (once, by cable):** Setup tab → Install, type a label like "Headset 07". In the headset, tick "Always allow from this computer".
2. **After every power on:** put on the headset and tap **"Always allow on this network"**. Without it, close game and reboot do not work. Everything else works.
3. **If the card shows "Not set up" or "Key rejected":** set the headset up again by cable.

## Repository

| Folder | What |
|---|---|
| `server/` | Server: Python, FastAPI, SQLite |
| `dashboard/` | Dashboard: React, Vite, TypeScript, Tailwind |
| `agent/` | Headset app: Android, Kotlin |
| `packaging/` | Builds the Arena program for Mac and Windows |
| `scripts/` | `start.sh` (dev server), `provision.sh` (headset setup by cable) |
| `docs/` | How things work, decisions, checks on the real headset |
| `spike/` | Old test app, not used in the product |

Each folder has its own `README.md` with build and run steps.

## Documentation

- [docs/status.md](docs/status.md): what is done and what is next.
- [docs/decisions.md](docs/decisions.md): why things are built this way.
- [docs/protocol.md](docs/protocol.md): messages between headsets, server and dashboard.
- [docs/features/](docs/features/): one file per feature (protection, power, statistics, updates…).
- [packaging/README.md](packaging/README.md): how to build the program and make a release.
