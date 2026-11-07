"""
Установка агента на шлемы через adb: список подключённых шлемов, установка с настройкой,
обновление, удаление. Это единственное место сервера, где есть ADB, и только для настройки:
управление шлемами по-прежнему идёт через агента.
"""

import asyncio
import base64
import datetime as dt
import hashlib
import logging
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID

from . import paths
from .protocol import SetupDevice, SetupJob

log = logging.getLogger(__name__)

PKG = "com.arena.agent"
A11Y = f"{PKG}/{PKG}.WatcherService"
RECEIVER = f"{PKG}/.ProvisionReceiver"
POWER_KEYS = ("power_button_long_press", "power_button_very_long_press")
AUTH_WAIT_S = 120
# Обновляться по Wi-Fi умеет только агент начиная с этой версии: первый раз нужен кабель
WIFI_UPDATE_MIN = (0, 11, 2)
SERIAL_RE = re.compile(r"^[A-Za-z0-9_.:\-]+$")


class SetupError(Exception):
    """Понятная оператору причина, почему шаг не удался."""


def _adb_sync(args: list[str], env: dict[str, str] | None, timeout: float) -> tuple[int, str]:
    adb = paths.adb_path()
    if adb is None:
        raise SetupError("adb not found")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # без чёрного окна
    try:
        p = subprocess.run(
            [adb, *args], capture_output=True, text=True, errors="replace",
            timeout=timeout, env=env, creationflags=flags,
        )
    except subprocess.TimeoutExpired as e:
        raise SetupError(f"adb timed out: {args[0]}") from e
    return p.returncode, (p.stdout + p.stderr).strip()


async def adb(*args: str, env: dict[str, str] | None = None, timeout: float = 30) -> tuple[int, str]:
    return await asyncio.to_thread(_adb_sync, list(args), env, timeout)


async def _shell(serial: str, command: str, **kw) -> str:
    code, out = await adb("-s", serial, "shell", command, **kw)
    if code != 0:
        raise SetupError(out[:300] or f"command failed: {command}")
    return out


def local_server_url(port: int) -> str:
    """Адрес компьютера в локальной сети: пакет никуда не уходит, система только выбирает интерфейс."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))
        return f"http://{s.getsockname()[0]}:{port}"


def _version(name: str | None) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in (name or "").split("."))
    except ValueError:
        return None


def fleet_status(agent_version: str | None, bundled_version: str) -> str:
    """Статус агента по версии из его hello: кабеля тут нет, спросить у шлема можно только так."""
    installed, bundled = _version(agent_version), _version(bundled_version)
    if installed is None or bundled is None:
        return "unknown"
    if installed == bundled:
        return "current"
    if installed > bundled:
        return "newer"
    return "needs_cable" if installed < WIFI_UPDATE_MIN else "outdated"


def agent_sha256() -> str:
    return hashlib.sha256(paths.agent_apk().read_bytes()).hexdigest()


def _status(installed_code: int | None, bundled_code: int) -> str:
    if installed_code is None:
        return "not_installed"
    if installed_code < bundled_code:
        return "outdated"
    return "newer" if installed_code > bundled_code else "current"


async def list_devices(labels: dict[str, tuple[str, str]]) -> list[SetupDevice]:
    """labels: серийный номер → (id шлема, название) из базы."""
    bundled_name, bundled_code = paths.bundled_agent()
    code, out = await adb("devices", "-l")
    if code != 0:
        raise SetupError(out[:300])
    devices = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2 or parts[0].startswith("*"):
            continue
        adb_id, state = parts[0], parts[1]
        transport = "wifi" if ":" in adb_id else "usb"
        device = SetupDevice(
            adb_id=adb_id, transport=transport, state=state, status=state,
            bundled_version=bundled_name,
        )
        if state == "device":
            await _fill_device(device, labels, bundled_code)
        devices.append(device)
    return devices


async def _fill_device(d: SetupDevice, labels: dict[str, tuple[str, str]], bundled_code: int) -> None:
    d.serial = (await _shell(d.adb_id, "getprop ro.serialno")).strip()
    d.model = (await _shell(d.adb_id, "getprop ro.product.model")).strip()
    if d.serial in labels:
        d.headset_id, d.label = labels[d.serial]
    dump = await _shell(d.adb_id, f"dumpsys package {PKG}")
    name = re.search(r"versionName=(\S+)", dump)
    code = re.search(r"versionCode=(\d+)", dump)
    d.installed_version = name.group(1) if name else None
    installed_code = int(code.group(1)) if code else None
    d.status = _status(installed_code, bundled_code)
    if installed_code is not None:
        a11y = await _shell(d.adb_id, "settings get secure enabled_accessibility_services")
        d.permissions_ok = (
            "WRITE_SECURE_SETTINGS: granted=true" in dump
            and "android.permission.DUMP: granted=true" in dump
            and A11Y in a11y
        )


class SetupJobs:
    """Одна операция за раз: при настройке ключа перезапускается adb-сервер."""

    def __init__(self, register: Callable[[str, str, str | None], Awaitable[tuple[str, str]]], port: int) -> None:
        self._register = register
        self._port = port
        self.current: SetupJob | None = None
        self.last_devices: list[SetupDevice] = []

    @property
    def busy(self) -> bool:
        return self.current is not None and self.current.status in ("running", "waiting_user")

    def start(self, kind: str, adb_id: str, label: str | None) -> SetupJob:
        if self.busy:
            raise SetupError("another operation is in progress")
        if not SERIAL_RE.match(adb_id):
            raise SetupError("bad device id")
        job = SetupJob(id=secrets.token_hex(8), kind=kind, adb_id=adb_id, status="running")
        self.current = job
        steps = {"install": self._install, "update": self._update, "remove": self._remove}[kind]
        asyncio.create_task(self._run(job, steps, label))
        return job

    async def _run(self, job: SetupJob, steps, label: str | None) -> None:
        try:
            await steps(job, label)
            job.status = "done"
            job.log.append("Done")
        except SetupError as e:
            job.status, job.error = "failed", str(e)
        except Exception as e:
            log.exception("setup job failed")
            job.status, job.error = "failed", f"{type(e).__name__}: {e}"

    async def _install_apk(self, job: SetupJob) -> None:
        job.log.append("Installing the agent…")
        code, out = await adb("-s", job.adb_id, "install", "-r", str(paths.agent_apk()), timeout=180)
        if code != 0:
            if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out:
                raise SetupError("Installed agent is signed with another key. Remove it first, then install")
            raise SetupError(out[-300:])

    async def _grant(self, job: SetupJob) -> None:
        s = job.adb_id
        job.log.append("Granting permissions…")
        await _shell(s, f"pm grant {PKG} android.permission.WRITE_SECURE_SETTINGS")
        await _shell(s, f"pm grant {PKG} android.permission.DUMP")
        await _shell(s, f"appops set {PKG} GET_USAGE_STATS allow")
        current = await _shell(s, "settings get secure enabled_accessibility_services")
        if A11Y not in current:
            services = A11Y if current in ("", "null") else f"{current}:{A11Y}"
            await _shell(s, f"settings put secure enabled_accessibility_services {services}")
        await _shell(s, "settings put secure accessibility_enabled 1")
        await _shell(s, "settings put global adb_allowed_connection_time 0")

    async def _broadcast(self, adb_id: str, action: str, extras: dict[str, str], env=None) -> str:
        args = ["-s", adb_id, "shell", "am", "broadcast", "-n", RECEIVER, "-a", f"{PKG}.{action}"]
        for key, value in extras.items():
            args += ["--es", key, value]
        code, out = await adb(*args, env=env)
        if code != 0 or 'data="ok' not in out:
            raise SetupError(f"agent rejected {action}")  # в out могут быть ключ и токен — не показываем
        return out

    async def _install(self, job: SetupJob, label: str | None) -> None:
        if not label:
            raise SetupError("headset name is required")
        if ":" in job.adb_id:
            raise SetupError("first install needs a USB cable")
        await self._install_apk(job)
        await self._grant(job)

        job.log.append("Registering the headset…")
        serial = (await _shell(job.adb_id, "getprop ro.serialno")).strip()
        ping = await self._broadcast(job.adb_id, "PROVISION_PING", {})
        android_id = m.group(1) if (m := re.search(r"android_id=([0-9a-f]+)", ping)) else None
        headset_id, token = await self._register(label, serial, android_id)
        await self._broadcast(job.adb_id, "PROVISION", {
            "server_url": local_server_url(self._port), "headset_id": headset_id, "token": token,
        })
        await self._provision_key(job)

    async def _provision_key(self, job: SetupJob) -> None:
        """Отдельный ключ шлема: шлему показываем только его, иначе разрешится ключ компьютера."""
        tmp = Path(tempfile.mkdtemp(prefix="arena-key-"))
        android_home = tmp / ".android"
        android_home.mkdir(mode=0o700)
        env = {
            **os.environ, "HOME": str(tmp), "USERPROFILE": str(tmp), "ANDROID_USER_HOME": str(android_home),
        }
        env.pop("ADB_VENDOR_KEYS", None)
        try:
            await adb("keygen", str(android_home / "adbkey"))
            pub = (android_home / "adbkey.pub").read_text(encoding="utf-8").split()[0]
            await adb("kill-server")
            await adb("start-server", env=env)

            job.status = "waiting_user"
            job.log.append(
                "Put on the headset, tick “Always allow from this computer” and press Allow"
            )
            deadline = asyncio.get_running_loop().time() + AUTH_WAIT_S
            while True:
                code, out = await adb("-s", job.adb_id, "get-state", env=env)
                if code == 0 and out.strip() == "device":
                    break
                if asyncio.get_running_loop().time() > deadline:
                    raise SetupError("Not allowed in the headset within 2 minutes")
                await asyncio.sleep(2)
            job.status = "running"

            # Без галочки ключ не сохранится, и беспроводная отладка его не примет
            await asyncio.sleep(1)
            _, logcat = await adb("-s", job.adb_id, "logcat", "-d", "-s", "AdbDebuggingManager:D", env=env, timeout=60)
            lines = [line for line in logcat.splitlines() if "Logging key" in line and pub[:40] in line]
            if not lines or "alwaysAllow = true" not in lines[-1]:
                raise SetupError("“Always allow from this computer” was not ticked. Run install again")

            job.log.append("Sending the ADB key to the agent…")
            key_der, cert_der = _key_and_cert(android_home / "adbkey")
            await self._broadcast(job.adb_id, "PROVISION_KEY", {
                "key_b64": base64.b64encode(key_der).decode(),
                "cert_b64": base64.b64encode(cert_der).decode(),
            }, env=env)
        finally:
            await adb("kill-server")
            await adb("start-server")
            shutil.rmtree(tmp, ignore_errors=True)  # ключ остаётся только в агенте

    async def _update(self, job: SetupJob, _: str | None) -> None:
        await self._install_apk(job)
        await self._grant(job)

    async def _remove(self, job: SetupJob, _: str | None) -> None:
        s = job.adb_id
        job.log.append("Restoring the power button and sleep…")
        for key in POWER_KEYS:
            await _shell(s, f"settings delete global {key}")
        await _shell(s, "am broadcast -a com.oculus.vrpowermanager.automation_disable")
        job.log.append("Removing the agent…")
        code, out = await adb("-s", s, "uninstall", PKG, timeout=60)
        if code != 0:
            raise SetupError(out[-300:])


def _key_and_cert(key_path: Path) -> tuple[bytes, bytes]:
    """Сертификат как у самого adb: самоподписанный CA. Возвращает PKCS#8 DER и X.509 DER."""
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Android"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Adb"),
    ])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1)
        .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_der = key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return key_der, cert.public_bytes(serialization.Encoding.DER)
