# dashboard: React + Vite + TypeScript + Tailwind

## Development

```bash
# 1. server (in another terminal)
cd ../server && HM_ADMIN_TOKEN=dev-admin uv run headset-server
# 2. optional: fake headsets
cd ../server && HM_ADMIN_TOKEN=dev-admin uv run python tools/fake_agent.py --count 3
# 3. dashboard with hot reload
npm run dev        # http://localhost:5173, /api and /live go to :8000
```

Server on another machine: `HM_SERVER=http://192.168.50.74:8000 npm run dev`.

## At the arena

`npm run build` → FastAPI serves `dist/` at http://<server>:8000/. No Node needed.

## Protocol types

`src/api/protocol.gen.ts` and `src/api/rest.gen.ts` are generated from the server's Pydantic models. Never edit them by hand:

```bash
npm run gen:types
```

## Code map

- `src/api/useLive.ts`: WebSocket `/live`. Snapshot of all headsets, then changes. Reconnects by itself.
- `src/lib/format.ts`: app names, ADB statuses in plain words, "N min ago".
- `src/components/`: headset card, summary, server connection status, command panel.
