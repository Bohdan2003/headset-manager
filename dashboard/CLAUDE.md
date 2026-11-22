# dashboard: React + Vite + TypeScript + Tailwind

How to run: `README.md` in this folder.

## Rules

- All text in the UI is in English. Terms: headset, Protection, Sleep, Request access.
- `src/api/protocol.gen.ts` and `src/api/rest.gen.ts` are generated. Never edit them by hand: `npm run gen:types`.
- No Next.js, no SSR. FastAPI serves `dist/`. In development `npm run dev` proxies `/api` and `/live` to `:8000`.
- Before "done": `npm run lint` and `npm run build`.
- Show statuses in plain words with a hint for the operator (what to do), not raw codes.

## What is on the screen

- **Summary tiles:** online, in game, battery < 20 % (also counts connected controllers), waiting for confirmation, setup needed.
- **Headset card:** label (click to rename: Enter saves, Esc cancels), online/offline with "N min ago", battery with "charging / not charging", controllers, current app (game or "Not in game · Meta menu"), 🛡 next to the protected game, ADB status in plain words, temperature, agent version, last command result, "asleep", update progress.
- **Selection:** choose several headsets, "select all online". Command panel: game from the games installed on the selected headsets, Protection switch (on / off / partly), Close game, Restart game, Sleep, Power off, Reboot (confirm for reboot and power off), Request access (only if some selected headsets are not `ready`). Hint "available on N of M". Buttons are disabled if only sleeping headsets are selected.
- **Games list:** only VR apps (`vr: true`) not from `com.oculus.`, `com.meta.`, `com.facebook.`, `com.android.`.
- **Statistics tab** (`#stats`, `#stats/7d`): headset health charts, tables by headset and by game, refresh once a minute. See `docs/features/stats.md`.
- **Setup tab:** only from the server computer. See `docs/features/provisioning.md`.
- **Login:** see `docs/features/auth.md`.

## Code map

- `src/api/useLive.ts`: WebSocket `/live`, snapshot then changes, reconnects by itself.
- `src/lib/format.ts`: app names, ADB statuses in plain words, "N min ago".
- `src/components/`: headset card, summary, server connection status.
