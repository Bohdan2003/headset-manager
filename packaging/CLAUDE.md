# packaging: the Arena program and CI

How to build: `README.md` in this folder.

## Arena program

One program: double click starts the server, opens the dashboard and shows a window with the address and the buttons Open dashboard / Stop / Reset password.
Inside: the dashboard build, `adb`, the agent (`prebuilt/agent.apk`, updated when you build on the Mac).

- Mac: `dist/Arena.app`. Windows: folder `dist/Arena` with `Arena.exe` (move the whole folder).
- Data is in the user folder (Mac: `~/Library/Application Support/Arena`, Windows: `%APPDATA%\Arena`): `headsets.db`, `admin-token.txt`, `auth.json`, `arena.log`. **Never delete the database:** it holds headset tokens.
- `./scripts/start.sh` uses its own database `server/headsets.db`. A copy of it was moved into the program on 04.11.
- The program is installed at the arena by hand: a restart breaks the connection to the headsets.
- Checked: tests with a fake adb, `Arena.app` start, migrations, dashboard. **Not checked:** Install/Update/Remove on a real headset, `Arena.exe` on a real Windows.

## CI/CD (`.github/workflows/`)

- `ci.yml`, on every push: server tests, dashboard lint and build, types match the server, agent compiles.
- `release.yml`: Mac and Windows builds on a `v*` tag (archives in Releases) or by hand (archives only on the run page).
- GitHub has no signing key, so the agent is not rebuilt there: it takes `prebuilt/agent.apk` (`ARENA_PREBUILT_AGENT=1`). `build.py` stops if its version does not match the code. So after an agent change: build on the Mac and commit the new `prebuilt/`.
- `gh` is not logged in on this computer. Check runs on the website.
- Node.js 20 warning in Actions: raise action versions later.
