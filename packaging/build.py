"""
Сборка программы Arena: python packaging/build.py

Mac: dist/Arena.app. Windows: папка dist/Arena с Arena.exe (папка, а не один файл: один .exe
при каждом запуске распаковывается во временную папку, откуда потом работал бы adb-сервер).

Агент берётся из packaging/prebuilt/agent.apk. На Mac файл обновляется при каждой сборке,
на Windows и в GitHub Actions (ARENA_PREBUILT_AGENT=1) используется как есть: агент должен быть
подписан одним ключом, иначе обновить уже установленного агента не получится.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
WORK = ROOT / "build"
PREBUILT = ROOT / "packaging" / "prebuilt"
SEP = ";" if sys.platform == "win32" else ":"
WINDOWS_ADB = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"

sys.path.insert(0, str(SERVER / "src"))


def run(cmd: list[str], cwd: Path) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == "win32")


def build_agent() -> None:
    """Только на Mac: там лежит ключ подписи агента."""
    from headset_server.paths import read_gradle_version

    run(["./gradlew", "assembleDebug", "-q"], ROOT / "agent")
    PREBUILT.mkdir(exist_ok=True)
    shutil.copy(ROOT / "agent/app/build/outputs/apk/debug/app-debug.apk", PREBUILT / "agent.apk")
    name, code = read_gradle_version(ROOT / "agent/app/build.gradle.kts")
    (PREBUILT / "version.json").write_text(json.dumps({"name": name, "code": code}))


def check_prebuilt_agent() -> None:
    """Готовый APK должен быть той версии, что в коде, иначе в сборку попадёт старый агент."""
    from headset_server.paths import read_gradle_version

    if not (PREBUILT / "agent.apk").exists():
        raise SystemExit("packaging/prebuilt/agent.apk is missing: build on the Mac first")
    name, code = read_gradle_version(ROOT / "agent/app/build.gradle.kts")
    built = json.loads((PREBUILT / "version.json").read_text())
    if (built["name"], built["code"]) != (name, code):
        raise SystemExit(
            f"packaging/prebuilt/agent.apk is {built['name']}, the code is {name}: rebuild it on the Mac"
        )


def collect_adb(target: Path) -> None:
    target.mkdir(parents=True)
    if sys.platform == "win32":
        with urllib.request.urlopen(WINDOWS_ADB) as r, zipfile.ZipFile(io.BytesIO(r.read())) as z:
            for name in ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"):
                (target / name).write_bytes(z.read(f"platform-tools/{name}"))
    else:
        adb = shutil.which("adb")
        if adb is None:
            raise SystemExit("adb not found")
        shutil.copy(Path(adb).resolve(), target / "adb")


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    resources = WORK / "resources"

    if sys.platform == "darwin" and not os.environ.get("ARENA_PREBUILT_AGENT"):
        build_agent()
    check_prebuilt_agent()
    run(["npm", "ci", "--no-audit", "--no-fund"], ROOT / "dashboard")
    run(["npm", "run", "build"], ROOT / "dashboard")

    collect_adb(resources / "adb")
    shutil.copytree(PREBUILT, resources / "agent")

    run(
        [
            "uv", "run", "pyinstaller", "--noconfirm", "--windowed", "--name", "Arena",
            "--osx-bundle-identifier", "com.arena.server",
            "--distpath", str(ROOT / "dist"), "--workpath", str(WORK / "pyi"), "--specpath", str(WORK),
            "--paths", str(SERVER / "src"),
            "--add-data", f"{ROOT / 'dashboard' / 'dist'}{SEP}dashboard",
            "--add-data", f"{resources / 'agent'}{SEP}agent",
            "--add-binary", f"{resources / 'adb'}{SEP}adb",
            "--add-data", f"{SERVER / 'src/headset_server/migrations'}{SEP}headset_server/migrations",
            "--hidden-import", "aiosqlite",
            "--hidden-import", "sqlalchemy.dialects.sqlite.aiosqlite",
            "--hidden-import", "headset_server.db",
            "--collect-submodules", "alembic",
            "--collect-data", "alembic",
            "--collect-submodules", "uvicorn",
            str(ROOT / "packaging" / "arena_main.py"),
        ],
        SERVER,
    )
    print("Built:", "dist/Arena/Arena.exe" if sys.platform == "win32" else "dist/Arena.app")


if __name__ == "__main__":
    main()
