"""
Вход на дашборд по общему паролю. Шлемы сюда не относятся: у агентов свои токены.
Пароль хранится только в виде хеша (scrypt). Сессия — подписанная cookie, поэтому
перезапуск сервера никого не разлогинивает, а смена пароля разлогинивает всех.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

COOKIE = "arena_session"
SESSION_S = 30 * 24 * 3600
MIN_PASSWORD = 8
MAX_FAILS = 5
LOCK_S = 30


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


class Auth:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._fails: dict[str, tuple[int, float]] = {}

    def _read(self) -> dict[str, str] | None:
        try:
            return json.loads(self._path.read_text())
        except (FileNotFoundError, ValueError):
            return None

    @property
    def configured(self) -> bool:
        return self._read() is not None

    def set_password(self, password: str) -> None:
        salt = os.urandom(16)
        data = {
            "salt": base64.b64encode(salt).decode(),
            "hash": base64.b64encode(_hash(password, salt)).decode(),
            "secret": secrets.token_hex(32),  # новый секрет: старые сессии перестают действовать
        }
        self._path.touch(mode=0o600)
        self._path.write_text(json.dumps(data))

    def reset(self) -> None:
        self._path.unlink(missing_ok=True)

    def verify(self, password: str) -> bool:
        data = self._read()
        if data is None:
            return False
        salt, expected = base64.b64decode(data["salt"]), base64.b64decode(data["hash"])
        return hmac.compare_digest(_hash(password, salt), expected)

    def locked_for(self, client: str) -> int:
        """Сколько секунд ещё ждать этому адресу после серии неверных паролей."""
        fails, until = self._fails.get(client, (0, 0.0))
        return max(0, int(until - time.monotonic()) + 1) if fails >= MAX_FAILS and until > time.monotonic() else 0

    def record_fail(self, client: str) -> None:
        fails, until = self._fails.get(client, (0, 0.0))
        if fails >= MAX_FAILS and until <= time.monotonic():
            fails = 0
        fails += 1
        self._fails[client] = (fails, time.monotonic() + LOCK_S if fails >= MAX_FAILS else 0.0)

    def clear_fails(self, client: str) -> None:
        self._fails.pop(client, None)

    def _sign(self, expires: str, secret: str) -> str:
        return hmac.new(secret.encode(), expires.encode(), hashlib.sha256).hexdigest()

    def make_session(self) -> str:
        data = self._read()
        if data is None:
            raise ValueError("password is not set")
        expires = str(int(time.time()) + SESSION_S)
        return f"{expires}.{self._sign(expires, data['secret'])}"

    def session_valid(self, value: str | None) -> bool:
        data = self._read()
        if data is None or not value or "." not in value:
            return False
        expires, signature = value.split(".", 1)
        if not expires.isdigit() or int(expires) < time.time():
            return False
        return hmac.compare_digest(signature, self._sign(expires, data["secret"]))
