# Building the Arena program

## Mac

```bash
cd server && uv run python ../packaging/build.py
```

Result: `dist/Arena.app`. Needs uv, Node.js, JDK 17 (`JAVA_HOME`), the Android SDK and adb.
The build updates `packaging/prebuilt/agent.apk`.

The program is not signed with an Apple certificate. On another Mac, the first start is: right click → Open.

## Windows

The exe can be built only on Windows. Needs uv and Node.js. No Android SDK needed.

1. Copy the project together with `packaging/prebuilt/` (the ready agent, built on the Mac).
2. Run:

   ```bat
   cd server
   uv run python ..\packaging\build.py
   ```

Result: folder `dist\Arena` with `Arena.exe`. Move the whole folder. The script downloads adb for Windows by itself.

For a USB connection to the headset on Windows you may need the Oculus ADB Driver.
On the first start Windows Firewall asks to allow incoming connections. Without it headsets can't connect.

We do not rebuild the agent on Windows: it must be signed with the same key as on the Mac.

## GitHub Actions

Checks on every push: `.github/workflows/ci.yml`. Build: `.github/workflows/release.yml`.

- A `v*` tag (for example `git tag v1.2.0 && git push origin v1.2.0`) builds Mac and Windows and puts the archives in Releases.
- A manual run (Actions → Build Arena → Run workflow) only builds: archives are on the run page, no release is created.

GitHub machines have no signing key, so the agent is not rebuilt there: it takes `packaging/prebuilt/agent.apk` from the repository (`ARENA_PREBUILT_AGENT=1`). If the agent version in the code changed, first build the program on the Mac and commit the new `packaging/prebuilt/`. Otherwise the build stops with an error.
