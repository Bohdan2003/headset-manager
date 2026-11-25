---
name: release
description: Prepare a release of the Arena program (checks, versions, tag). Pushing and tagging only after the user says yes. The user starts it by typing /release.
disable-model-invocation: true
---

# Release

Details: `packaging/CLAUDE.md` and `packaging/README.md`.

1. **Checks.**
   - `cd server && uv run pytest`
   - `cd dashboard && npm run lint && npm run build`
   - `cd dashboard && npm run gen:types && git diff --exit-code src/api/` (types match the server)
   - `cd agent && JAVA_HOME=/opt/homebrew/opt/openjdk@17 ./gradlew assembleDebug`
2. **Agent version.** If the agent changed: build the program on the Mac (`cd server && uv run python ../packaging/build.py`) so `packaging/prebuilt/agent.apk` and `version.json` match the code. CI stops otherwise.
3. **Review.** Run the `reviewer` role on the changes since the last tag (give it the range `<last tag>..HEAD`; find the tag with `git describe --tags --abbrev=0`). No tags yet (first release): agree on the start commit with the user. Uncommitted changes: a second run without a range.
4. **Notes.** Short release notes in simple English from `docs/progress/` and `git log`.
5. **Ask the user** for the version number and for "yes". Then: commit, `git tag vX.Y.Z`, `git push origin main vX.Y.Z`. GitHub builds Mac and Windows archives into Releases.
6. **Update `docs/tasks/BOARD.md` and `docs/progress/<today>.md`.** Remind the user: the program is installed at the arena by hand, and a restart breaks headset connections for a moment.
