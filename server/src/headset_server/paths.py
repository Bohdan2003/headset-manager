"""
Где лежат файлы. В собранной программе ресурсы (дашборд, adb, агент, миграции) внутри неё
и только для чтения, а база и настройки — в папке пользователя, чтобы обновление их не затирало.
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

PACKAGED = getattr(sys, "frozen", False)
_REPO = Path(__file__).resolve().parents[3]


def resource_dir() -> Path:
    """Папка с ресурсами собранной программы (только когда PACKAGED)."""
    return Path(sys._MEIPASS)  # type: ignore[attr-defined]


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "Arena"
    path.mkdir(parents=True, exist_ok=True)
    return path


def dashboard_dir() -> Path:
    return resource_dir() / "dashboard" if PACKAGED else _REPO / "dashboard" / "dist"


def adb_path() -> str | None:
    if PACKAGED:
        return str(resource_dir() / "adb" / ("adb.exe" if sys.platform == "win32" else "adb"))
    return shutil.which("adb")


def agent_apk() -> Path:
    if PACKAGED:
        return resource_dir() / "agent" / "agent.apk"
    return _REPO / "agent" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"


def bundled_agent() -> tuple[str, int]:
    """Версия агента, которую поставит программа: (versionName, versionCode)."""
    if PACKAGED:
        info = json.loads((resource_dir() / "agent" / "version.json").read_text())
        return info["name"], info["code"]
    return read_gradle_version(_REPO / "agent" / "app" / "build.gradle.kts")


def read_gradle_version(path: Path) -> tuple[str, int]:
    text = path.read_text()
    name = re.search(r'versionName = "([^"]+)"', text)
    code = re.search(r"versionCode = (\d+)", text)
    if not name or not code:
        raise ValueError(f"no version in {path}")
    return name.group(1), int(code.group(1))
