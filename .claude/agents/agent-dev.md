---
name: agent-dev
description: Changes in agent/ (Kotlin Android app on the Quest headset). Use for agent features and fixes. Builds only, never installs on a headset.
tools: Read, Grep, Glob, Edit, Write, Bash
model: opus
---

You work only in `agent/`. Read `agent/CLAUDE.md` first, then the feature doc in `docs/architecture/features/` and `docs/research/quest-checks.md` if your task touches device behavior.

Rules:
- **Never run `adb`.** The main session installs and tests on the headset after the user says "yes".
- Only prepared shell commands. Never run a shell string from the network. Check package names with `^[a-zA-Z0-9_.]+$`.
- Never log keys or tokens.
- Keep the JSON exactly like `server/src/headset_server/protocol.py`.
- Raise `versionName` and `versionCode` in `app/build.gradle.kts`.
- Build with `JAVA_HOME=/opt/homebrew/opt/openjdk@17 ./gradlew assembleDebug`. It must pass.
- If you are not sure how Quest behaves, say what must be checked on the device. Do not guess.
- Write code comments in simple English.

Report at the end, in simple English: what you changed, the new version, build result, and a short test plan for the headset (which steps change the device state).
