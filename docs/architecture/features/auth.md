# Dashboard login (07.11)

One shared password. Code: `server/src/headset_server/auth.py`.

- The password is stored as a scrypt hash in `auth.json` (in the program: in the data folder next to the database).
- Login = a signed cookie for 30 days (`httponly`, `samesite=strict`, no `Secure`: the server works over http in the local network, so the password is not encrypted on the way).
- After 5 wrong passwords the address is blocked for 30 s.
- First start: the password can be set only from the server computer. Forgot it: the Reset password button in the Arena window. All sessions stop working.
- Closed: `/api/*` and `WS /live`. Open: `/health`, `/api/auth/*`, `/api/agent/apk`, `WS /agent` (agents have their own tokens). `provision.sh` uses `HM_ADMIN_TOKEN`.
- An open `/live` connection is not closed on a password reset. REST returns 401 and shows the login on the next action.
