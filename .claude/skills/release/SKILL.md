---
name: release
description: Prepare a release of the Arena program (checks, versions, tag). Pushing and tagging only after the user says yes.
disable-model-invocation: true
---

# Release

Details: `packaging/CLAUDE.md` and `packaging/README.md`.

1. **Checks.**
   - `cd server && uv run pytest`
   - `cd dashboard && npm run lint && npm run build`
   - `cd dashboard && npm run gen:types && git diff --exit-code src/api/` (types match the server)
   - `cd agent && ./gradlew assembleDebug`
2. **Agent version.** If the agent changed: build the program on the Mac (`cd server && uv run python ../packaging/build.py`) so `packaging/prebuilt/agent.apk` and `version.json` match the code. CI stops otherwise.
3. **Review.** Run the `reviewer` role on the changes since the last tag (`git log <last tag>..HEAD`).
4. **Notes.** Short release notes in simple English from `docs/status.md` and `git log`.
5. **Ask the user** for the version number and for "yes". Then: commit, `git tag vX.Y.Z`, `git push origin main vX.Y.Z`. GitHub builds Mac and Windows archives into Releases.
6. **Update `docs/status.md`.** Remind the user: the program is installed at the arena by hand, and a restart breaks headset connections for a moment.
